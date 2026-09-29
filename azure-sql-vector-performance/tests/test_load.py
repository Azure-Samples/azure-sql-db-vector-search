from contextlib import ExitStack, redirect_stdout
import io
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import benchmark
import load


class LoadTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory())).resolve()
        self.stack.enter_context(redirect_stdout(io.StringIO()))
        self.stack.enter_context(patch.object(load.shutil, "which", side_effect=lambda name: name))
        self.stack.enter_context(patch.object(load, "SIZES", {"10M": 5, "100M": 9}))
        self.stack.enter_context(patch.object(load, "DIMENSIONS", 3))
        self.stack.enter_context(patch.object(load, "QUERY_COUNT", 3))
        self.dataset = self.root / "yfcc-images-10M"
        self.dataset.mkdir()
        self.output_dir = self.dataset / "bcp"
        self.documents = [struct.pack("<3f", *values) for values in (
            (0.5, -1.25, -0.0), (1.0, 2.5, -3.75), (0.125, 128.0, -32.0),
            (0.0, 1.0, 2.0), (3.0, 4.0, 5.0),
        )]
        self.queries = [struct.pack("<3f", *values) for values in (
            (-4.5, 0.0, 0.5), (2.0, -1.0, 3.0), (0.5, 1.5, -2.5),
        )]
        (self.dataset / "base.bin").write_bytes(struct.pack("<II", 5, 3) + b"".join(self.documents))
        (self.dataset / "queries.bin").write_bytes(struct.pack("<II", 3, 3) + b"".join(self.queries))
        (self.dataset / "groundtruth.bin").write_bytes(
            struct.pack("<II6i6f", 3, 2, 2, 0, 1, 2, 4, 3, 0.125, 2.5, 0.5, 4.0, 1.0, 8.0)
        )
        self.args = dict(size="10M", data_dir=self.root, server="localhost,1433",
                         database="Vector Test", username="benchmark_user", batch_size=1, chunk_rows=2)
        self.imports = []
        self.verifications = []
        self.pending_chunk = None
        self.reported_version = "18.6.1.1"
        self.bcp_help = "-n -z[0|1] -b -e -m -u -U -T"
        self.sqlcmd_help = "-S -d -U -b -i -v -C -E"
        self.fail_setup = False
        self.fail_import = None
        self.reject_import = None
        self.fail_verification = None
        self.run = self.stack.enter_context(patch.object(load.subprocess, "run", side_effect=self.run_tool))

    def run_tool(self, command, **kwargs):
        if command[-1] == "-v":
            return subprocess.CompletedProcess(command, 0, f"Version: {self.reported_version}\n", "")
        if command[-1] == "-?":
            return subprocess.CompletedProcess(command, 0, self.sqlcmd_help, "")
        if len(command) == 1:
            return subprocess.CompletedProcess(command, 1, self.bcp_help, "")
        if "in" in command:
            self.assertIsNone(self.pending_chunk)
            native = Path(command[command.index("in") + 1])
            self.assertEqual(list(self.output_dir.glob("*.bcp")), [native])
            self.assertFalse(list(self.output_dir.glob("*.part")))
            self.imports.append((command[1], native.read_bytes()))
            self.pending_chunk = native
            if len(self.imports) == self.reject_import:
                Path(command[command.index("-e") + 1]).write_bytes(b"rejected row")
            if len(self.imports) == self.fail_import:
                raise subprocess.CalledProcessError(1, command)
        elif "-i" in command:
            script = Path(command[command.index("-i") + 1])
            self.assertTrue(script.is_file())
            if script.name == "create-table.sql":
                self.assertFalse(self.imports)
                self.assertFalse(list(self.output_dir.iterdir()))
                if self.fail_setup:
                    raise subprocess.CalledProcessError(1, command)
            else:
                self.assertEqual(script.name, "load-data.sql")
                self.assertTrue(self.pending_chunk.is_file())
                variables = dict(value.split("=", 1) for value in command[command.index("-v") + 1:])
                self.verifications.append(variables)
                if len(self.verifications) == self.fail_verification:
                    raise subprocess.CalledProcessError(1, command)
                self.pending_chunk = None
        return subprocess.CompletedProcess(command, 0, "", "")

    def test_vector_records_preserve_ids_headers_and_float32_bytes(self):
        load.load_data(**self.args)
        for table, vectors in (("documents", self.documents), ("queries", self.queries)):
            with self.subTest(table=table):
                payload = b"".join(payload for name, payload in self.imports if name == f"dbo.yfcc_10M_{table}")
                record_size = 4 + 2 + 8 + 12
                self.assertEqual(len(payload), len(vectors) * record_size)
                for row_id, vector in enumerate(vectors):
                    record = payload[row_id * record_size:(row_id + 1) * record_size]
                    self.assertEqual(struct.unpack("<iH", record[:6]), (row_id, 20))
                    self.assertEqual(record[6:14], bytes.fromhex("a9 01 03 00 00 00 00 00"))
                    self.assertEqual(record[14:], vector)

    def test_ground_truth_reorders_id_and_distance_blocks_into_rows(self):
        load.load_data(**self.args)
        payload = b"".join(payload for name, payload in self.imports if name.endswith("_groundtruth"))
        self.assertEqual(list(struct.iter_unpack("<iiif", payload)), [
            (0, 1, 2, 0.125), (0, 2, 0, 2.5), (1, 1, 1, 0.5), (1, 2, 2, 4.0),
            (2, 1, 4, 1.0), (2, 2, 3, 8.0),
        ])

    def test_multiple_chunks_partial_tail_and_cleanup_after_verification(self):
        load.load_data(**self.args)
        self.assertEqual([len(payload) for name, payload in self.imports], [52, 52, 26, 52, 26, 64, 32])
        self.assertEqual([int(values["FirstId"]) for values in self.verifications], [0, 2, 4, 0, 2, 0, 2])
        self.assertEqual([int(values["EndId"]) for values in self.verifications], [2, 4, 5, 2, 3, 2, 3])
        self.assertEqual([int(values["ExpectedRows"]) for values in self.verifications], [2, 2, 1, 2, 1, 4, 2])
        self.assertEqual([int(values["ExpectedTotal"]) for values in self.verifications], [5, 5, 5, 3, 3, 6, 6])
        self.assertEqual(self.verifications[-1]["IdColumn"], "query_id")
        self.assertFalse(list(self.output_dir.iterdir()))

    def test_bcp_batch_size_is_independent_of_chunk_rows(self):
        load.load_data(**{**self.args, "batch_size": 7})
        self.assertEqual(len(self.imports), 7)
        for call in self.run.call_args_list:
            command = call.args[0]
            if "in" in command:
                self.assertEqual(command[command.index("-b") + 1], "7")

    def test_native_tools_password_prompts_and_script_variables(self):
        load.load_data(**self.args)
        for call in self.run.call_args_list:
            command = call.args[0]
            if "-S" not in command:
                continue
            self.assertTrue(call.kwargs["check"])
            self.assertNotIn("-P", command)
            self.assertNotIn("-T", command)
            self.assertNotIn("stdin", call.kwargs)
            self.assertNotIn("input", call.kwargs)
            self.assertNotIn("shell", call.kwargs)
            self.assertNotIn("capture_output", call.kwargs)
            self.assertIn("Vector Test", command)
            if "in" in command:
                self.assertIn("-n", command)
                self.assertIn("-z0", command)
                self.assertNotIn("-u", command)
            else:
                self.assertNotIn("-C", command)
                script = Path(command[command.index("-i") + 1])
                variables = dict(value.split("=", 1) for value in command[command.index("-v") + 1:])
                import re
                self.assertEqual(set(re.findall(r"\$\((\w+)\)", script.read_text())), set(variables))

    def test_setup_guard_uses_database_names_before_creating_tables(self):
        script = (load.ROOT / "scripts/setup/create-table.sql").read_text(encoding="utf-8")
        guard = script[script.index("IF DB_NAME()"):script.index("THROW 50000")]
        self.assertEqual(" ".join(guard.split()),
                         "IF DB_NAME() <> N'$(ExpectedDatabase)' "
                         "OR DB_NAME() IN (N'master', N'tempdb', N'model', N'msdb')")
        self.assertNotIn("DB_ID(", script.upper())
        self.assertLess(script.index("THROW 50000"), script.index("BEGIN TRANSACTION"))
        self.assertLess(script.index("THROW 50000"), script.index("CREATE TABLE"))
        self.run.assert_not_called()

    def test_trust_server_certificate_uses_each_tools_switch(self):
        load.load_data(**self.args, trust_server_certificate=True)
        for call in self.run.call_args_list:
            command = call.args[0]
            if "-S" in command:
                self.assertIn("-u" if "in" in command else "-C", command)

    def test_trusted_connection_uses_windows_authentication_without_passwords(self):
        load.load_data(**{**self.args, "username": None, "trusted_connection": True})
        self.assertEqual(len(self.imports), 7)
        for call in self.run.call_args_list:
            command = call.args[0]
            if "-S" in command:
                self.assertIn("-T" if "in" in command else "-E", command)
                self.assertNotIn("-U", command)
                self.assertNotIn("-P", command)
                self.assertNotIn("input", call.kwargs)

    def test_trusted_connection_rejects_conflicting_or_missing_authentication(self):
        for username, trusted_connection in (("benchmark_user", True), (None, False)):
            with self.subTest(username=username), self.assertRaisesRegex(ValueError, "either"):
                load.load_data(**{**self.args, "username": username, "trusted_connection": trusted_connection})
        self.run.assert_not_called()
        self.assertFalse(self.output_dir.exists())

    def test_source_files_are_not_modified(self):
        before = {path: path.read_bytes() for path in self.dataset.glob("*.bin")}
        load.load_data(**self.args)
        for path, payload in before.items():
            self.assertEqual(path.read_bytes(), payload)

    def test_existing_native_output_is_not_overwritten(self):
        self.output_dir.mkdir()
        existing = self.output_dir / "documents.bcp"
        existing.write_bytes(b"existing")
        with self.assertRaises(FileExistsError):
            load.load_data(**self.args)
        self.assertEqual(existing.read_bytes(), b"existing")
        self.run.assert_not_called()

    def test_short_headers_truncated_and_trailing_files_fail_before_tools(self):
        for filename in ("base.bin", "queries.bin", "groundtruth.bin"):
            path = self.dataset / filename
            original = path.read_bytes()
            for malformed in (b"short", original[:-1], original + b"extra"):
                with self.subTest(filename=filename, length=len(malformed)):
                    path.write_bytes(malformed)
                    with self.assertRaises(ValueError):
                        load.load_data(**self.args)
                    self.assertFalse(self.output_dir.exists())
            path.write_bytes(original)
        self.run.assert_not_called()

    def test_wrong_dataset_dimensions_query_count_and_depth_fail_before_tools(self):
        for filename, rows, width in (
            ("base.bin", 7, 3), ("base.bin", 5, 4), ("queries.bin", 3, 4),
            ("queries.bin", 2, 3), ("groundtruth.bin", 2, 2),
            ("groundtruth.bin", 3, 0), ("groundtruth.bin", 3, 6),
        ):
            path = self.dataset / filename
            original = path.read_bytes()
            with self.subTest(filename=filename, rows=rows, width=width):
                path.write_bytes(struct.pack("<II", rows, width) + original[8:])
                with self.assertRaises(ValueError):
                    load.load_data(**self.args)
                path.write_bytes(original)
        self.run.assert_not_called()

    def test_old_and_unknown_bcp_versions_fail_before_sql_or_staging(self):
        for version in ("18.6.1.0", "17.0.4055.5", "unknown"):
            with self.subTest(version=version):
                self.reported_version = version
                with self.assertRaisesRegex(ValueError, "18.6.1.1"):
                    load.load_data(**self.args)
                self.assertFalse(self.output_dir.exists())
        self.assertEqual(len(self.run.call_args_list), 3)

    def test_missing_native_bcp_option_or_sqlcmd_option_fails_before_staging(self):
        for attribute, help_text in (("bcp_help", "-n -b -e -m"), ("sqlcmd_help", "-S -d -U -b -i")):
            with self.subTest(tool=attribute), patch.object(self, attribute, help_text):
                with self.assertRaisesRegex(ValueError, "options"):
                    load.load_data(**self.args)
                self.assertFalse(self.output_dir.exists())

    def test_sql_target_or_schema_failure_happens_before_conversion(self):
        self.fail_setup = True
        with patch.object(load, "write_vector_chunk") as encode, self.assertRaises(subprocess.CalledProcessError):
            load.load_data(**self.args)
        encode.assert_not_called()
        self.assertFalse(list(self.output_dir.iterdir()))

    def test_nonfinite_later_chunk_retains_partial_without_importing_it(self):
        path = self.dataset / "base.bin"
        payload = bytearray(path.read_bytes())
        struct.pack_into("<f", payload, 8 + 2 * 12, float("nan"))
        path.write_bytes(payload)
        with self.assertRaisesRegex(ValueError, "source ID 2"):
            load.load_data(**self.args)
        self.assertEqual(len(self.imports), 1)
        self.assertEqual([path.name for path in self.output_dir.iterdir()], ["documents-0000000002.bcp.part"])

    def test_duplicate_gt_neighbor_fails_before_setup_or_staging(self):
        path = self.dataset / "groundtruth.bin"
        payload = bytearray(path.read_bytes())
        struct.pack_into("<2i", payload, 8, 1, 1)
        path.write_bytes(payload)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            load.load_data(**self.args)
        self.run.assert_not_called()
        self.assertFalse(self.output_dir.exists())

    def test_bad_gt_values_even_at_last_query_fail_before_any_tools(self):
        path = self.dataset / "groundtruth.bin"
        original = path.read_bytes()
        for offset, format, value in ((8, "<i", 8572694), (8 + 5 * 4, "<i", -1),
                                      (8 + 6 * 4 + 5 * 4, "<f", float("nan"))):
            with self.subTest(value=value):
                payload = bytearray(original)
                struct.pack_into(format, payload, offset, value)
                path.write_bytes(payload)
                with self.assertRaises(ValueError):
                    load.load_data(**self.args)
                self.run.assert_not_called()
                self.assertFalse(self.output_dir.exists())

    def test_setup_failure_allows_corrected_attempt_with_empty_staging(self):
        self.fail_setup = True
        with self.assertRaises(subprocess.CalledProcessError):
            load.load_data(**self.args)
        self.assertFalse(list(self.output_dir.iterdir()))
        self.fail_setup = False
        load.load_data(**self.args)
        self.assertEqual(len(self.imports), 7)

    def test_empty_staging_does_not_bypass_sql_setup_refusal(self):
        self.output_dir.mkdir()
        self.fail_setup = True
        with self.assertRaises(subprocess.CalledProcessError):
            load.load_data(**self.args)
        self.assertFalse(self.imports)

    def test_native_import_failure_stops_without_retry_or_cleanup(self):
        self.fail_import = 2
        with self.assertRaises(subprocess.CalledProcessError):
            load.load_data(**self.args)
        self.assertEqual(len(self.imports), 2)
        self.assertEqual(len(self.verifications), 1)
        self.assertEqual(sorted(path.name for path in self.output_dir.iterdir()),
                         ["documents-0000000002.bcp", "documents-0000000002.errors.txt"])

    def test_zero_exit_with_rejected_rows_retains_chunk_and_error_file(self):
        self.reject_import = 1
        with self.assertRaisesRegex(ValueError, "rejected rows"):
            load.load_data(**self.args)
        self.assertEqual(len(self.imports), 1)
        self.assertFalse(self.verifications)
        self.assertTrue((self.output_dir / "documents-0000000000.bcp").exists())
        self.assertEqual((self.output_dir / "documents-0000000000.errors.txt").read_bytes(), b"rejected row")

    def test_count_verification_failure_retains_chunk_and_stops(self):
        self.fail_verification = 2
        with self.assertRaises(subprocess.CalledProcessError):
            load.load_data(**self.args)
        self.assertEqual(len(self.imports), 2)
        self.assertEqual(len(self.verifications), 2)
        self.assertTrue((self.output_dir / "documents-0000000002.bcp").exists())
        self.assertTrue((self.output_dir / "documents-0000000002.errors.txt").exists())

    def test_inherited_password_is_not_used(self):
        with patch.dict(load.os.environ, {"SQLCMDPASSWORD": "test-only-placeholder",
                                         "OSQLPASSWORD": "test-only-placeholder"}):
            load.load_data(**self.args)
        for call in self.run.call_args_list:
            self.assertNotIn("SQLCMDPASSWORD", call.kwargs["env"])
            self.assertNotIn("OSQLPASSWORD", call.kwargs["env"])

    def test_wsl_tool_and_file_paths(self):
        self.assertEqual(load.tool_command("bcp", None, "Ubuntu"),
                         ["wsl.exe", "--distribution", "Ubuntu", "--exec", "/opt/mssql-tools18/bin/bcp"])
        self.assertEqual(load.tool_command("bcp", "/custom/bcp", "Ubuntu")[-1], "/custom/bcp")
        path = self.root / "with spaces.bcp"
        with patch.object(load.subprocess, "check_output", return_value="/mnt/c/with spaces.bcp\n") as convert:
            self.assertEqual(load.tool_path(path, "Ubuntu"), "/mnt/c/with spaces.bcp")
        self.assertEqual(convert.call_args.args[0][-1], str(path.resolve()))

    def test_invalid_wsl_translation_fails_before_sql_or_staging(self):
        with patch.object(load, "check_tools"), patch.object(load.subprocess, "check_output", return_value=""):
            with self.assertRaisesRegex(ValueError, "absolute Linux path"):
                load.load_data(**self.args, wsl="Ubuntu")
        self.assertFalse(self.output_dir.exists())
        self.run.assert_not_called()

    def test_dispatcher_runs_load_script_and_preserves_exit_code(self):
        self.run.side_effect = None
        self.run.return_value = subprocess.CompletedProcess([], 1)
        self.assertEqual(benchmark.main(["load", "--size", "10M"]), 1)
        command = self.run.call_args.args[0]
        self.assertEqual(command[0], sys.executable)
        self.assertEqual(Path(command[1]), load.ROOT / "load.py")
        self.assertEqual(command[2:], ["--size", "10M"])

    def test_invalid_size_or_chunk_or_batch_size_stops_before_any_output(self):
        for key, value in (("size", "1M"), ("size", "1m"), ("size", "10M; DROP TABLE x"), ("batch_size", 0), ("batch_size", -1),
                           ("chunk_rows", 0), ("chunk_rows", -1)):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                load.load_data(**{**self.args, key: value})
        self.assertFalse((self.dataset / "bcp").exists())
        self.run.assert_not_called()


class ChunkEncodingTests(unittest.TestCase):
    def test_vector_chunks_preserve_ids_payloads_and_original_prefix(self):
        vectors = [struct.pack("<1280f", *[row_id + index / 16 for index in range(1280)])
                   for row_id in range(5)]
        source = io.BytesIO(b"".join(vectors))
        combined = bytearray()
        for start in range(0, 5, 2):
            output = io.BytesIO()
            load.write_vector_chunk(source, output, start, min(2, 5 - start), 1280)
            combined.extend(output.getvalue())
        expected = b"".join(
            struct.pack("<i", row_id) + struct.pack("<HBBHB3x", 5128, 0xA9, 1, 1280, 0) + vector
            for row_id, vector in enumerate(vectors)
        )
        self.assertEqual(combined, expected)

    def test_vectors_reject_nonfinite_values_and_short_reads(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "source ID 7"):
                load.write_vector_chunk(io.BytesIO(struct.pack("<f", value)), io.BytesIO(), 7, 1, 1)
        with self.assertRaises(EOFError):
            load.write_vector_chunk(io.BytesIO(b"short"), io.BytesIO(), 0, 1, 3)

    def test_groundtruth_chunks_keep_block_layout_ranks_and_query_ids(self):
        neighbors = io.BytesIO(struct.pack("<6i", 2, 0, 1, 2, 0, 1))
        distances = io.BytesIO(struct.pack("<6f", 0.125, 2.5, 0.5, 4, 1, 8))
        output = io.BytesIO()
        load.write_groundtruth_chunk(neighbors, distances, output, 0, 2, 2, 3)
        load.write_groundtruth_chunk(neighbors, distances, output, 2, 1, 2, 3)
        self.assertEqual(list(struct.iter_unpack("<iiif", output.getvalue())), [
            (0, 1, 2, 0.125), (0, 2, 0, 2.5), (1, 1, 1, 0.5),
            (1, 2, 2, 4), (2, 1, 0, 1), (2, 2, 1, 8),
        ])

    def test_groundtruth_rejects_bad_neighbors_and_distances(self):
        for neighbors in ((-1, 0), (3, 0), (1, 1)):
            with self.subTest(neighbors=neighbors), self.assertRaises(ValueError):
                load.write_groundtruth_chunk(io.BytesIO(struct.pack("<2i", *neighbors)),
                                             io.BytesIO(struct.pack("<2f", 0, 1)), io.BytesIO(), 0, 1, 2, 3)
        for value in (float("nan"), float("inf"), -1.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                load.write_groundtruth_chunk(io.BytesIO(struct.pack("<2i", 0, 1)),
                                             io.BytesIO(struct.pack("<2f", 0, value)), io.BytesIO(), 0, 1, 2, 3)

    def test_published_1m_out_of_range_neighbor_is_not_silently_remapped(self):
        neighbors = io.BytesIO(struct.pack("<2i", 8572694, 7797918))
        distances = io.BytesIO(struct.pack("<2f", 0.2934209108352661, 0.3084106147289276))
        output = io.BytesIO()
        with self.assertRaisesRegex(ValueError, r"query 0, rank 1: neighbor ID 8572694.*0\.\.999999"):
            load.write_groundtruth_chunk(neighbors, distances, output, 0, 1, 2, 1000000)
        self.assertEqual(output.getvalue(), b"")


if __name__ == "__main__":
    unittest.main()