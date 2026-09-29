import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import load


@unittest.skipUnless(os.environ.get("MSSQL_VECTOR_LIVE_TEST") == "1", "live SQL test is opt-in")
class LiveLoadTests(unittest.TestCase):
    def test_native_bcp_round_trip(self):
        server = os.environ["MSSQL_VECTOR_TEST_SERVER"]
        database = os.environ["MSSQL_VECTOR_TEST_DATABASE"]
        username = os.environ["MSSQL_VECTOR_TEST_USERNAME"]
        bcp = os.environ["MSSQL_VECTOR_TEST_BCP"]
        sqlcmd = os.environ["MSSQL_VECTOR_TEST_SQLCMD"]
        trust_server_certificate = os.environ.get("MSSQL_VECTOR_TEST_TRUST_SERVER_CERTIFICATE") == "1"

        data_dir = Path(tempfile.mkdtemp(prefix="yfcc-live-load-")).resolve()
        print(f"Live fixture artifacts retained in {data_dir}; no SQL cleanup is performed.", flush=True)
        with patch.dict(load.SIZES, {"10M": 3}), patch.object(load, "QUERY_COUNT", 2):
            dataset = data_dir / "yfcc-images-10M"
            dataset.mkdir()
            documents = [
                struct.pack("<1280f", *[((index + seed) % 257 - 128) / 16 for index in range(1280)])
                for seed in (0, 17, 101)
            ]
            queries = [
                struct.pack("<1280f", *[((index * step) % 127 - 63) / 8 for index in range(1280)])
                for step in (3, 11)
            ]
            (dataset / "base.bin").write_bytes(struct.pack("<II", 3, 1280) + b"".join(documents))
            (dataset / "queries.bin").write_bytes(struct.pack("<II", 2, 1280) + b"".join(queries))
            (dataset / "groundtruth.bin").write_bytes(
                struct.pack("<II6i6f", 2, 3, 2, 0, 1, 1, 2, 0, 0.125, 2.5, 4.0, 0.5, 1.25, 8.0)
            )

            load.load_data(
                size="10M", data_dir=data_dir, server=server, database=database, username=username,
                bcp=bcp, sqlcmd=sqlcmd, batch_size=1, chunk_rows=2,
                trust_server_certificate=trust_server_certificate,
            )
            self.assertFalse(list((dataset / "bcp").iterdir()))

            trust_option = ["-u"] if trust_server_certificate else []
            environment = os.environ.copy()
            environment.pop("SQLCMDPASSWORD", None)
            environment.pop("OSQLPASSWORD", None)
            expected = {
                table: b"".join(struct.pack("<i", row_id)
                                + bytes.fromhex("08 14 a9 01 00 05 00 00 00 00") + vector
                                for row_id, vector in enumerate(vectors))
                for table, vectors in (("documents", documents), ("queries", queries))
            }
            expected["groundtruth"] = b"".join(struct.pack("<iiif", *row) for row in (
                (0, 1, 2, 0.125), (0, 2, 0, 2.5), (0, 3, 1, 4.0),
                (1, 1, 1, 0.5), (1, 2, 2, 1.25), (1, 3, 0, 8.0),
            ))
            queries_by_table = {
                "documents": "SELECT id, embedding FROM dbo.yfcc_10M_documents ORDER BY id",
                "queries": "SELECT id, embedding FROM dbo.yfcc_10M_queries ORDER BY id",
                "groundtruth": (
                    "SELECT query_id, rank, neighbor_id, distance "
                    "FROM dbo.yfcc_10M_groundtruth ORDER BY query_id, rank"
                ),
            }
            for table, query in queries_by_table.items():
                exported = data_dir / f"{table}-export.bcp"
                subprocess.run(
                    [bcp, query, "queryout", str(exported), "-n", "-z0", "-U", username, "-S", server,
                     "-d", database, *trust_option],
                    check=True, env=environment,
                )
                self.assertEqual(exported.read_bytes(), expected[table])


if __name__ == "__main__":
    unittest.main()