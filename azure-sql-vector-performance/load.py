import argparse
from contextlib import ExitStack
import math
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

from download import DEFAULT_DATA_DIR, SIZES


ROOT = Path(__file__).resolve().parent
DIMENSIONS = 1280
QUERY_COUNT = 100000
MIN_BCP_VERSION = (18, 6, 1, 1)


def tool_command(name, executable, wsl):
    if wsl:
        return ["wsl.exe", "--distribution", wsl, "--exec", executable or f"/opt/mssql-tools18/bin/{name}"]
    return [shutil.which(executable or name) or executable or name]


def tool_path(path, wsl):
    path = Path(path).resolve()
    if not wsl:
        return str(path)
    translated = subprocess.check_output(
        ["wsl.exe", "--distribution", wsl, "--exec", "wslpath", "-a", "-u", str(path)],
        text=True,
    ).strip()
    if not translated.startswith("/"):
        raise ValueError(f"WSL did not return an absolute Linux path for {path}.")
    return translated


def check_tools(bcp_command, sqlcmd_command, environment, trust_server_certificate, trusted_connection=False):
    version = subprocess.run(bcp_command + ["-v"], check=True, capture_output=True,
                             text=True, env=environment).stdout
    match = re.search(r"Version:\s*(\d+)\.(\d+)\.(\d+)\.(\d+)\b", version, re.IGNORECASE)
    if not match or tuple(map(int, match.groups())) < MIN_BCP_VERSION:
        raise ValueError("BCP must report version 18.6.1.1 or newer for native float32 vectors.")
    print(version.strip(), flush=True)
    bcp_help = subprocess.run(bcp_command, check=False, capture_output=True, text=True, env=environment)
    sqlcmd_help = subprocess.run(sqlcmd_command + ["-?"], check=True, capture_output=True,
                                text=True, env=environment)
    for name, result, options in (
        ("BCP", bcp_help, ["-n", "-z", "-b", "-e", "-m", "-T" if trusted_connection else "-U"]
         + (["-u"] if trust_server_certificate else [])),
        ("sqlcmd", sqlcmd_help, ["-S", "-d", "-E" if trusted_connection else "-U", "-b", "-i", "-v"]
         + (["-C"] if trust_server_certificate else [])),
    ):
        help_text = result.stdout + result.stderr
        if any(option not in help_text for option in options):
            raise ValueError(f"{name} does not advertise the required command-line options.")


def validate_sources(dataset, size):
    shapes = {}
    for filename in ("base.bin", "queries.bin", "groundtruth.bin"):
        path = dataset / filename
        with path.open("rb") as source:
            header = source.read(8)
        if len(header) != 8:
            raise ValueError(f"Incomplete header in {filename}.")
        rows, width = struct.unpack("<II", header)
        expected_rows = SIZES[size] if filename == "base.bin" else QUERY_COUNT
        if rows != expected_rows:
            raise ValueError(f"{filename}: expected {expected_rows} rows, found {rows}.")
        if filename == "groundtruth.bin":
            if not 1 <= width <= SIZES[size]:
                raise ValueError("Ground-truth depth must be between 1 and the document count.")
            expected_bytes = 8 + rows * width * 8
        else:
            if width != DIMENSIONS:
                raise ValueError(f"{filename}: expected {DIMENSIONS} dimensions, found {width}.")
            expected_bytes = 8 + rows * width * 4
        if path.stat().st_size != expected_bytes:
            raise ValueError(f"{filename}: expected exactly {expected_bytes} bytes.")
        shapes[filename] = (rows, width)
    return shapes


def write_vector_chunk(source, output, chunk_start, count, dimensions):
    vector_bytes = dimensions * 4
    prefix = struct.pack("<HBBI2x", vector_bytes + 8, 0xA9, 1, dimensions)
    for row_offset in range(count):
        vector = source.read(vector_bytes)
        if len(vector) != vector_bytes:
            raise EOFError("Incomplete vector data.")
        if not all(math.isfinite(value) for (value,) in struct.iter_unpack("<f", vector)):
            raise ValueError(f"Non-finite vector at source ID {chunk_start + row_offset}.")
        output.write(struct.pack("<i", chunk_start + row_offset))
        output.write(prefix)
        output.write(vector)


def groundtruth_rows(neighbors, distances, chunk_start, count, depth, document_count):
    for row_offset in range(count):
        neighbor_bytes = neighbors.read(depth * 4)
        distance_bytes = distances.read(depth * 4)
        if len(neighbor_bytes) != depth * 4 or len(distance_bytes) != depth * 4:
            raise EOFError("Incomplete ground-truth data.")
        query_id = chunk_start + row_offset
        neighbor_ids = struct.unpack(f"<{depth}i", neighbor_bytes)
        for rank, neighbor_id in enumerate(neighbor_ids, start=1):
            if not 0 <= neighbor_id < document_count:
                raise ValueError(
                    f"Ground-truth query {query_id}, rank {rank}: neighbor ID {neighbor_id} is outside "
                    f"the document ID range 0..{document_count - 1}. "
                    "Use ground truth matching this corpus; do not remap or discard invalid IDs."
                )
        if len(set(neighbor_ids)) != depth:
            raise ValueError(f"Duplicate ground-truth neighbors for query {query_id}.")
        if not all(math.isfinite(value) and value >= 0
                   for (value,) in struct.iter_unpack("<f", distance_bytes)):
            raise ValueError(f"Invalid ground-truth distance for query {query_id}.")
        yield query_id, neighbor_bytes, distance_bytes


def write_groundtruth_chunk(neighbors, distances, output, chunk_start, count, depth, document_count):
    for query_id, neighbor_bytes, distance_bytes in groundtruth_rows(
            neighbors, distances, chunk_start, count, depth, document_count):
        for rank_offset in range(depth):
            offset = rank_offset * 4
            output.write(struct.pack("<ii", query_id, rank_offset + 1))
            output.write(neighbor_bytes[offset:offset + 4])
            output.write(distance_bytes[offset:offset + 4])


def load_data(size, data_dir, server, database, username=None, wsl=None, bcp=None, sqlcmd=None, batch_size=10000,
              trust_server_certificate=False, chunk_rows=100000, trusted_connection=False):
    if size not in SIZES or batch_size < 1 or chunk_rows < 1:
        raise ValueError("Choose a supported size and positive chunk and batch sizes.")
    if (username and trusted_connection) or (not username and not trusted_connection):
        raise ValueError("Choose either a SQL username or a trusted connection, not both.")
    dataset = Path(data_dir).resolve() / f"yfcc-images-{size}"
    output_dir = dataset / "bcp"
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        raise FileExistsError(f"Inspect existing staging files before loading: {output_dir}")
    shapes = validate_sources(dataset, size)
    query_count, depth = shapes["groundtruth.bin"]
    print("Validating all ground-truth IDs, distances, and unique neighbors before loading.", flush=True)
    with (dataset / "groundtruth.bin").open("rb") as neighbors, (dataset / "groundtruth.bin").open("rb") as distances:
        neighbors.seek(8)
        distances.seek(8 + query_count * depth * 4)
        for _ in groundtruth_rows(neighbors, distances, 0, query_count, depth, SIZES[size]):
            pass
    bcp_command = tool_command("bcp", bcp, wsl)
    sqlcmd_command = tool_command("sqlcmd", sqlcmd, wsl)
    connection = ["-S", server, "-d", database]
    bcp_auth = ["-T"] if trusted_connection else ["-U", username]
    sqlcmd_auth = ["-E"] if trusted_connection else ["-U", username]
    bcp_options = connection + bcp_auth + ["-n", "-z0", "-b", str(batch_size), "-m", "1"]
    if trust_server_certificate:
        bcp_options.append("-u")
    environment = os.environ.copy()
    environment.pop("SQLCMDPASSWORD", None)
    environment.pop("OSQLPASSWORD", None)
    check_tools(bcp_command, sqlcmd_command, environment, trust_server_certificate, trusted_connection)
    sqlcmd_command += connection + sqlcmd_auth + ["-b"] + (["-C"] if trust_server_certificate else [])
    create_script = tool_path(ROOT / "scripts/setup/create-table.sql", wsl)
    verify_script = tool_path(ROOT / "scripts/setup/load-data.sql", wsl)
    staging_path = tool_path(output_dir, wsl)
    output_dir.mkdir(exist_ok=True)
    if wsl:
        for option, path in (("-d", staging_path), ("-r", create_script), ("-r", verify_script)):
            subprocess.run(["wsl.exe", "--distribution", wsl, "--exec", "test", option, path],
                           check=True, env=environment)

    print(f"Loading yfcc-images-{size} into {server}, database {database}", flush=True)
    print("Checking the SQL target and creating empty tables.", flush=True)
    if not trusted_connection:
        print("Enter your SQL password at each tool prompt.", flush=True)
    subprocess.run(
        sqlcmd_command + ["-i", create_script, "-v", f"DatasetSize={size}",
                          f"DocumentDimensions={shapes['base.bin'][1]}",
                          f"QueryDimensions={shapes['queries.bin'][1]}",
                          "ExpectedDatabase=" + database.replace("'", "''")],
        check=True, env=environment,
    )

    for filename, table in (("base.bin", "documents"), ("queries.bin", "queries"),
                            ("groundtruth.bin", "groundtruth")):
        row_count, width = shapes[filename]
        rows_per_source_row = width if table == "groundtruth" else 1
        with ExitStack() as files:
            source = files.enter_context((dataset / filename).open("rb"))
            source.seek(8)
            if table == "groundtruth":
                distances = files.enter_context((dataset / filename).open("rb"))
                distances.seek(8 + row_count * width * 4)
            for chunk_start in range(0, row_count, chunk_rows):
                count = min(chunk_rows, row_count - chunk_start)
                chunk_end = chunk_start + count
                native_path = output_dir / f"{table}-{chunk_start:010d}.bcp"
                partial = native_path.with_suffix(".bcp.part")
                errors = native_path.with_suffix(".errors.txt")
                print(f"Converting {table}: source rows {chunk_start:,} to {chunk_end - 1:,}", flush=True)
                with partial.open("xb") as output:
                    if table == "groundtruth":
                        write_groundtruth_chunk(source, distances, output, chunk_start, count,
                                                width, SIZES[size])
                    else:
                        write_vector_chunk(source, output, chunk_start, count, width)
                partial.rename(native_path)

                with errors.open("xb"):
                    pass
                subprocess.run(
                    bcp_command + [f"dbo.yfcc_{size}_{table}", "in", tool_path(native_path, wsl),
                                   "-e", tool_path(errors, wsl)] + bcp_options,
                    check=True, env=environment,
                )
                if errors.stat().st_size:
                    raise ValueError(f"BCP reported rejected rows. Inspect {errors} and {native_path}.")
                subprocess.run(
                    sqlcmd_command + ["-i", verify_script, "-v", f"TableName=yfcc_{size}_{table}",
                                      "IdColumn=" + ("query_id" if table == "groundtruth" else "id"),
                                      f"FirstId={chunk_start}", f"EndId={chunk_end}",
                                      f"ExpectedRows={count * rows_per_source_row}",
                                      f"TotalSourceRows={row_count}",
                                      f"ExpectedTotal={row_count * rows_per_source_row}"],
                    check=True, env=environment,
                )
                native_path.unlink()
                errors.unlink()
                print(f"Verified {table}: {chunk_end:,}/{row_count:,} source rows; chunk removed.", flush=True)

    print("Load complete. All chunk and final table counts verified; source files unchanged.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert and bulk-load YFCC data using native BCP.")
    parser.add_argument("--size", type=str.upper, choices=SIZES, required=True)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--server", required=True)
    parser.add_argument("--database", required=True)
    authentication = parser.add_mutually_exclusive_group(required=True)
    authentication.add_argument("--username", help="SQL login; each tool prompts for its password.")
    authentication.add_argument("--trusted-connection", action="store_true",
                                help="Use the current Windows identity without password prompts.")
    parser.add_argument("--wsl", metavar="DISTRO", help="Run BCP and sqlcmd in WSL from Windows.")
    parser.add_argument("--bcp", help="BCP executable path in the selected environment.")
    parser.add_argument("--sqlcmd", help="sqlcmd executable path in the selected environment.")
    parser.add_argument("--chunk-rows", type=int, default=100000,
                        help="Source rows per temporary file (GT: queries, not neighbor rows).")
    parser.add_argument("--batch-size", type=int, default=10000,
                        help="Rows per BCP transaction, independent of chunk size.")
    parser.add_argument(
        "--trust-server-certificate", action="store_true",
        help="Trust the SQL Server certificate (local/test servers only).",
    )
    args = parser.parse_args()
    try:
        load_data(**vars(args))
    except (OSError, ValueError, EOFError, struct.error, subprocess.CalledProcessError) as error:
        print(f"Load stopped: {error}. Files and any committed rows were retained. No retry was attempted.", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("Load cancelled. Files and any committed rows were retained.", file=sys.stderr)
        sys.exit(130)