import argparse
import csv
import getpass
import json
from pathlib import Path
import re
import sys
import uuid
import warnings

from download import SIZES


ROOT = Path(__file__).resolve().parent
TIMING_LABEL = "server-side CREATE VECTOR INDEX elapsed time"


def execute_and_consume(connection, sql, parameters=(), results=None):
    if results is None:
        results = []
    cursor = connection.cursor()
    try:
        cursor.execute(sql, *parameters)
        while True:
            description = cursor.description
            if description:
                columns = [column[0] for column in description]
                results.append([dict(zip(columns, row)) for row in cursor.fetchall()])
            if not cursor.nextset():
                return results
    finally:
        original_error = sys.exc_info()[1]
        try:
            cursor.close()
        except Exception:
            if original_error is None:
                raise


def quote_identifier(name):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", name):
        raise ValueError("Identifiers must contain only letters, digits, and underscores, up to 128 characters.")
    return f"[{name}]"


def read_population(connection, table, expected_rows):
    population = execute_and_consume(connection, f"""
        SELECT COUNT_BIG(*) AS row_count,
               COALESCE(SUM(CONVERT(BIGINT, CASE WHEN embedding IS NULL THEN 0 ELSE 1 END)), 0) AS nonnull_row_count,
               MIN(id) AS first_id, MAX(id) AS last_id
        FROM {table};
    """)[0][0]
    if (population["row_count"] != expected_rows or population["nonnull_row_count"] != expected_rows
            or population["first_id"] != 0 or population["last_id"] != expected_rows - 1):
        raise ValueError(f"Expected {expected_rows} non-null documents with IDs 0 through {expected_rows - 1}; "
                         f"found {population}.")
    return population


def validate_target(connection, database, table, expected_rows):
    target = execute_and_consume(connection, """
        SELECT CASE WHEN DB_NAME() = ? AND DB_NAME() NOT IN ('master', 'model', 'msdb', 'tempdb')
                    THEN 1 ELSE 0 END AS database_matches,
               OBJECT_ID(?, N'U') AS object_id,
               HAS_PERMS_BY_NAME(?, 'OBJECT', 'SELECT') AS can_select,
               HAS_PERMS_BY_NAME(?, 'OBJECT', 'ALTER') AS can_alter;
    """, (database, table, table, table))[0][0]
    if not target["database_matches"] or target["object_id"] is None:
        raise ValueError("Connect to the intended user database containing the loaded document table.")
    if target["can_select"] != 1 or target["can_alter"] != 1:
        raise ValueError("SELECT and ALTER permissions on the document table are required.")
    columns = execute_and_consume(connection, """
        SELECT vector_dimensions, vector_base_type, is_nullable, is_computed
        FROM sys.columns WHERE object_id = ? AND name = ?;
    """, (target["object_id"], "embedding"))[0]
    if (len(columns) != 1 or columns[0]["vector_dimensions"] != 1280
            or columns[0]["vector_base_type"] != 0 or columns[0]["is_nullable"]
            or columns[0]["is_computed"]):
        raise ValueError("Expected a non-null VECTOR(1280, float32) embedding column.")
    keys = execute_and_consume(connection, """
        SELECT columns.name, columns.system_type_id, columns.is_nullable,
               indexes.type, indexes.is_disabled
        FROM sys.indexes AS indexes
        JOIN sys.index_columns AS keys ON keys.object_id = indexes.object_id AND keys.index_id = indexes.index_id
        JOIN sys.columns AS columns ON columns.object_id = keys.object_id AND columns.column_id = keys.column_id
        WHERE indexes.object_id = ? AND indexes.is_primary_key = 1 AND keys.key_ordinal > 0;
    """, (target["object_id"],))[0]
    if (len(keys) != 1 or keys[0]["name"] != "id" or keys[0]["system_type_id"] != 56
            or keys[0]["is_nullable"] or keys[0]["type"] != 1 or keys[0]["is_disabled"]):
        raise ValueError("Expected an existing single-column clustered INT primary key on id.")
    return target["object_id"], read_population(connection, table, expected_rows)


def read_index(connection, table, index_name):
    return execute_and_consume(connection, """
        SELECT target.object_id, indexes.index_id, indexes.is_disabled,
               vectors.vector_index_type, vectors.distance_metric,
               CASE WHEN EXISTS (
                   SELECT 1 FROM sys.index_columns AS indexed
                   JOIN sys.columns AS columns ON columns.object_id = indexed.object_id
                                              AND columns.column_id = indexed.column_id
                   WHERE indexed.object_id = indexes.object_id AND indexed.index_id = indexes.index_id
                     AND columns.name = 'embedding') THEN 1 ELSE 0 END AS on_embedding
        FROM (SELECT OBJECT_ID(?, N'U') AS object_id) AS target
        LEFT JOIN sys.indexes AS indexes ON indexes.object_id = target.object_id AND indexes.name = ?
        LEFT JOIN sys.vector_indexes AS vectors ON vectors.object_id = indexes.object_id
                                               AND vectors.index_id = indexes.index_id;
    """, (table, index_name))[0][0]


def save_result(path, result):
    with path.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2, allow_nan=False)
        output.write("\n")


def save_csv_result(path, result):
    row = {name: json.dumps(value, allow_nan=False) if isinstance(value, (dict, list)) else value
           for name, value in result.items()}
    with path.open("x", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)


def recover_result(directory):
    directory = Path(directory)
    result = json.loads((directory / "request.json").read_text(encoding="utf-8"))
    for name in ("create-result.json", "result.json"):
        path = directory / name
        if path.exists():
            try:
                result.update(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                print(f"Could not read {path}; retaining the last intact checkpoint.", file=sys.stderr)
    if result["status"] in ("prepared", "create_succeeded"):
        result["status"] = "reporting_incomplete" if result.get("create_completed") else "incomplete"
        result["error"] = "Recovered checkpoint only. Inspect database state before another attempt."
    destination = directory / f"recovered-{uuid.uuid4()}.json"
    save_result(destination, result)
    save_csv_result(destination.with_suffix(".csv"), result)
    print(f"Recovered {result['status']}: {destination.with_suffix('.csv')}")
    return result


def build_index(size, server, database, output_dir, maxdop, expected_engine_version=None,
                username=None, trusted_connection=False, trust_server_certificate=False,
                index_name="yfcc_vector_index", repetition=1, replace_existing=False):
    if (size not in SIZES or not isinstance(maxdop, int) or maxdop < 0
            or not isinstance(repetition, int) or repetition < 1):
        raise ValueError("Choose a supported size, nonnegative MAXDOP, and positive repetition.")
    if bool(username) == bool(trusted_connection):
        raise ValueError("Choose a SQL username or a trusted connection, not both.")
    index = quote_identifier(index_name)
    table = f"[dbo].{quote_identifier(f'yfcc_{size}_documents')}"
    if expected_engine_version is not None and not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", expected_engine_version):
        raise ValueError("An optional engine pin must be an exact ProductVersion, for example 18.0.251.0.")
    if not server or not database or any(character in server + database + (username or "") for character in "\r\n\0"):
        raise ValueError("Server, database, and username must be nonempty where required and contain no control characters.")

    directory = Path(output_dir).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    create_sql = (f"CREATE VECTOR INDEX {index} ON {table} ([embedding])\n"
                  f"WITH (METRIC = 'euclidean', TYPE = 'DISKANN', MAXDOP = {maxdop});")
    result = {
        "run_id": str(uuid.uuid4()), "repetition": repetition, "started_utc": None,
        "dataset": f"yfcc-images-{size}", "expected_row_count": SIZES[size], "row_count": None,
        "dimension": 1280, "vector_type": "float32", "metric": "euclidean", "index_name": index_name,
        "table": table, "build_options": {"TYPE": "DISKANN", "omitted_options": "server defaults"},
        "maxdop": maxdop, "engine_version": None, "expected_engine_version": expected_engine_version,
        "service_configuration": None, "build_seconds": None, "status": "prepared",
        "create_completed": False, "create_sql": create_sql, "timing_label": TIMING_LABEL,
        "timer": "SYSUTCDATETIME / DATEDIFF_BIG(nanosecond), not monotonic",
        "cache_state": "uncontrolled; pre-build population validation may warm pages",
        "server": server, "database": database,
    }
    save_result(directory / "request.json", result)
    print(create_sql, flush=True)
    print(f"Timing: {TIMING_LABEL}. Attempt: {directory}", flush=True)
    connection = None
    password = None
    attributes = {}
    connection_string = None
    phase = "connect"
    try:
        import pyodbc

        pyodbc.pooling = False
        attributes = {"DRIVER": "ODBC Driver 18 for SQL Server", "SERVER": server, "DATABASE": database,
                      "Encrypt": "yes", "TrustServerCertificate": "yes" if trust_server_certificate else "no",
                      "ConnectRetryCount": "0"}
        if trusted_connection:
            attributes["Trusted_Connection"] = "yes"
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                password = getpass.getpass("SQL password: ")
            attributes.update(UID=username, PWD=password)
        connection_string = ";".join(name + "={" + value.replace("}", "}}") + "}" for name, value in attributes.items())
        connection = pyodbc.connect(connection_string, autocommit=True, timeout=15)
        connection_string = None
        attributes.clear()
        execute_and_consume(connection, "SET NOCOUNT ON; SET XACT_ABORT ON; SET IMPLICIT_TRANSACTIONS OFF; SET LOCK_TIMEOUT 10000;")

        phase = "validate"
        object_id, population = validate_target(connection, database, table, SIZES[size])
        result.update(population)
        metadata = execute_and_consume(connection, """
            SELECT CONVERT(NVARCHAR(128), SERVERPROPERTY('ProductVersion')) AS engine_version,
                   @@VERSION AS version_string, CONVERT(NVARCHAR(128), SERVERPROPERTY('Edition')) AS edition,
                   CONVERT(INT, SERVERPROPERTY('EngineEdition')) AS engine_edition,
                   DB_NAME() AS database_name, @@SERVERNAME AS server_name, ORIGINAL_LOGIN() AS login_name,
                   (SELECT compatibility_level FROM sys.databases WHERE name = DB_NAME()) AS compatibility_level,
                   (SELECT CONVERT(INT, value) FROM sys.database_scoped_configurations WHERE name = 'MAXDOP') AS database_maxdop,
                   (SELECT CONVERT(INT, value) FROM sys.database_scoped_configurations WHERE name = 'PREVIEW_FEATURES') AS preview_features;
        """)[0][0]
        result["engine_version"] = metadata.pop("engine_version")
        result["service_configuration"] = metadata
        if expected_engine_version is not None and result["engine_version"] != expected_engine_version:
            raise ValueError("Actual engine version differs from the explicitly requested pin.")
        existing = read_index(connection, table, index_name)
        if existing["object_id"] != object_id:
            raise ValueError("The target table changed during validation.")
        if existing["index_id"] is not None:
            if existing["vector_index_type"] is None:
                raise ValueError("The named index is not a vector index; it will not be replaced.")
            if not replace_existing:
                raise ValueError("Index already exists. Use --replace-existing only if replacement is intended.")
            answer = input(f"Drop only [{index_name}] on {table} before timing? Type the index name to confirm: ")
            if answer != index_name:
                raise ValueError("Existing index left unchanged; replacement was not authorized.")
            if read_index(connection, table, index_name) != existing:
                raise ValueError("Index state changed during confirmation; nothing was dropped.")
            phase = "drop"
            execute_and_consume(connection, f"DROP INDEX {index} ON {table};")

        phase = "create"
        timing_sql = (ROOT / "scripts/build-index.sql").read_text(encoding="utf-8")
        timing_results = []
        try:
            execute_and_consume(connection, timing_sql, (create_sql,), results=timing_results)
        finally:
            for rows in timing_results:
                if len(rows) == 1 and "create_completed" in rows[0]:
                    result.update(rows[0])
        if not result["create_completed"] or result["build_seconds"] is None:
            raise RuntimeError("CREATE completion was not confirmed; inspect database state before retrying.")
        result["status"] = "create_succeeded"
        save_result(directory / "create-result.json", result)

        phase = "verify"
        if result["build_seconds"] < 0:
            raise ValueError("The server clock moved backwards; this build duration is invalid.")
        created = read_index(connection, table, index_name)
        if (created["object_id"] != object_id or created["index_id"] is None or created["is_disabled"]
                or (created["vector_index_type"] or "").lower() != "diskann"
                or (created["distance_metric"] or "").lower() != "euclidean" or not created["on_embedding"]):
            raise ValueError("CREATE returned but the expected vector index could not be verified.")
        result["postbuild_population"] = read_population(connection, table, SIZES[size])
        result["status"] = "succeeded"
        phase = "export"
        save_csv_result(directory / "result.csv", result)
        save_result(directory / "result.json", result)
    except (Exception, KeyboardInterrupt) as error:
        result["status"] = ("reporting_failed" if result["create_completed"] else
                            "interrupted" if isinstance(error, KeyboardInterrupt) else "failed")
        result["error_phase"] = phase
        result["error_type"] = type(error).__name__
        message = str(error)
        if password:
            message = message.replace(password.replace("}", "}}"), "[redacted]").replace(password, "[redacted]")
        result["error"] = message
        try:
            save_result(directory / "result.json", result)
        except Exception:
            print(f"Could not save failure details in {directory}. Original error preserved; do not rebuild automatically.", file=sys.stderr)
        if not (directory / "result.csv").exists():
            try:
                save_csv_result(directory / "result.csv", result)
            except Exception:
                print(f"Could not export failure CSV in {directory}. Original error preserved.", file=sys.stderr)
        raise
    finally:
        original_error = sys.exc_info()[1]
        password = connection_string = None
        attributes.clear()
        try:
            if connection is not None:
                connection.close()
        except Exception:
            if original_error is None:
                raise
    print(f"{TIMING_LABEL}: {result['build_seconds']} seconds. Result: {directory / 'result.csv'}")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Measure one fresh vector index build using pyodbc and a server-side SQL timer.")
    parser.add_argument("--recover-result", type=Path, help="Export retained checkpoints only; never connect or rebuild.")
    parser.add_argument("--size", type=str.upper, choices=SIZES)
    parser.add_argument("--server")
    parser.add_argument("--database")
    parser.add_argument("--output-dir", type=Path, help="New directory for this attempt; existing directories are refused.")
    parser.add_argument("--maxdop", type=int, help="Required explicitly. 0 permits server-selected parallelism, not one worker.")
    parser.add_argument("--expected-engine-version", help="Optional exact ProductVersion pin; actual version is always recorded.")
    authentication = parser.add_mutually_exclusive_group()
    authentication.add_argument("--username")
    authentication.add_argument("--trusted-connection", action="store_true")
    parser.add_argument("--trust-server-certificate", action="store_true")
    parser.add_argument("--replace-existing", action="store_true", help="Allow prompting to replace only the named vector index.")
    parser.add_argument("--index-name", default="yfcc_vector_index")
    parser.add_argument("--repetition", type=int, default=1, help="Label only; each invocation builds once.")
    args = vars(parser.parse_args(argv))
    recovery = args.pop("recover_result")
    try:
        if recovery is not None:
            recover_result(recovery)
            return 0
        for name in ("size", "server", "database", "output_dir", "maxdop"):
            if args[name] is None:
                parser.error(f"--{name.replace('_', '-')} is required for a build")
        build_index(**args)
    except KeyboardInterrupt:
        print("Build interrupted. Inspect retained output and database state before retrying.", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"Build stopped ({type(error).__name__}). Inspect retained attempt files; no retry was performed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())