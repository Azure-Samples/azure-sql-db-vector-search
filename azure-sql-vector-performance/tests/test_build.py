from contextlib import redirect_stdout
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, PropertyMock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build
import benchmark


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name).resolve() / "attempt"
        self.args = dict(size="10M", server="localhost,1433", database="Vector Test",
                         output_dir=self.directory, maxdop=1, trusted_connection=True)
        self.target = dict(database_matches=1, object_id=42, can_select=1, can_alter=1)
        self.column = dict(vector_dimensions=1280, vector_base_type=0, is_nullable=False, is_computed=False)
        self.key = dict(name="id", system_type_id=56, is_nullable=False, type=1, is_disabled=False)
        self.population = dict(row_count=10000000, nonnull_row_count=10000000, first_id=0, last_id=9999999)
        self.existing = dict(object_id=42, index_id=None, is_disabled=False, vector_index_type=None,
                             distance_metric=None, on_embedding=False)
        self.created = dict(object_id=42, index_id=4, is_disabled=False, vector_index_type="DiskANN",
                            distance_metric="euclidean", on_embedding=True)
        self.timing = dict(create_completed=True, started_utc="2026-09-24T12:00:00Z", build_seconds=12.5)
        self.metadata = dict(engine_version="18.0.251.0", edition="Enterprise", version_string="DEBUG",
                             engine_edition=3, database_name="Vector Test", database_maxdop=0)
        self.create_error = None
        self.create_count = 0
        self.changed_index = False
        self.index_reads = 0
        self.calls = []
        self.events = []
        self.cursors = []
        self.connection = Mock()
        self.connection.cursor.side_effect = self.make_cursor
        self.driver = Mock()
        self.driver.connect.side_effect = self.connect
        driver_patch = patch.dict(sys.modules, {"pyodbc": self.driver})
        driver_patch.start()
        self.addCleanup(driver_patch.stop)
        self.stdout = redirect_stdout(io.StringIO())
        self.stdout.__enter__()
        self.addCleanup(self.stdout.__exit__, None, None, None)

    def connect(self, *args, **kwargs):
        self.events.append("connect")
        return self.connection

    def make_cursor(self):
        cursor = Mock()
        cursor.description = None
        cursor.nextset.return_value = False
        cursor.execute.side_effect = lambda sql, *parameters: self.run_sql(cursor, sql, parameters)
        self.cursors.append(cursor)
        return cursor

    def run_sql(self, cursor, sql, parameters):
        self.calls.append((sql, parameters))
        rows = []
        if sql.startswith("SET NOCOUNT"):
            label = "session"
        elif "AS database_matches" in sql:
            label, rows = "target", [self.target]
        elif "FROM sys.columns WHERE" in sql:
            label, rows = "column", [self.column]
        elif "keys.key_ordinal > 0" in sql:
            label, rows = "key", [self.key]
        elif "COUNT_BIG(*) AS row_count" in sql:
            label, rows = "population", [self.population]
        elif "SERVERPROPERTY('ProductVersion')" in sql:
            label, rows = "metadata", [self.metadata]
        elif "FROM (SELECT OBJECT_ID" in sql:
            self.index_reads += 1
            label = "index"
            rows = [self.created.copy() if self.create_count else self.existing.copy()]
            if self.changed_index and self.index_reads == 2:
                rows[0]["index_id"] = 99
            if self.create_count and self.create_error is None:
                self.assertTrue((self.directory / "create-result.json").exists())
        elif sql.startswith("DROP INDEX"):
            label = "drop"
        elif sql.startswith("DECLARE @create_sql"):
            self.create_count += 1
            label, rows = "create", [self.timing] if self.timing is not None else []
            if self.create_error:
                cursor.nextset.side_effect = self.create_error
        else:
            self.fail(f"Unexpected SQL: {sql}")
        self.events.append(label)
        if rows:
            cursor.description = [(name,) for name in rows[0]]
            cursor.fetchall.return_value = [tuple(row.values()) for row in rows]

    def test_one_connection_and_direct_workflow_with_server_timing(self):
        result = build.build_index(**self.args)
        self.assertEqual(self.events, ["connect", "session", "target", "column", "key", "population",
                                       "metadata", "index", "create", "index", "population"])
        self.driver.connect.assert_called_once()
        self.assertEqual(self.driver.connect.call_args.kwargs, {"autocommit": True, "timeout": 15})
        connection_string = self.driver.connect.call_args.args[0]
        self.assertIn("DRIVER={ODBC Driver 18 for SQL Server}", connection_string)
        self.assertIn("Encrypt={yes}", connection_string)
        self.assertIn("TrustServerCertificate={no}", connection_string)
        self.assertIn("Trusted_Connection={yes}", connection_string)
        self.assertIn("ConnectRetryCount={0}", connection_string)
        self.assertFalse(self.driver.pooling)
        self.assertEqual(self.create_count, 1)
        self.assertEqual(result["timing_label"], "server-side CREATE VECTOR INDEX elapsed time")
        self.assertEqual(result["row_count"], 10000000)
        self.assertEqual(result["build_seconds"], 12.5)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["maxdop"], 1)
        self.assertIn("MAXDOP = 1", result["create_sql"])
        self.assertEqual(json.loads((self.directory / "result.json").read_text())["run_id"], result["run_id"])
        timed_sql, parameters = next(call for call in self.calls if call[0].startswith("DECLARE @create_sql"))
        self.assertEqual(parameters, (result["create_sql"],))
        self.assertEqual(timed_sql.count("?"), 1)
        self.connection.close.assert_called_once()
        for cursor in self.cursors:
            cursor.nextset.assert_called_once()
            cursor.close.assert_called_once()

    def test_existing_destination_refused_without_sql(self):
        self.directory.mkdir()
        with self.assertRaises(FileExistsError):
            build.build_index(**self.args)
        self.driver.connect.assert_not_called()

    def test_success_exports_one_csv_row_with_metadata_and_exact_sql(self):
        self.metadata["version_string"] = 'Build, "DEBUG"\r\nSecond line'
        result = build.build_index(**self.args)
        with (self.directory / "result.csv").open(encoding="utf-8", newline="") as source:
            rows = list(csv.DictReader(source))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["run_id"], result["run_id"])
        self.assertEqual(rows[0]["status"], "succeeded")
        self.assertEqual(rows[0]["row_count"], "10000000")
        self.assertEqual(float(rows[0]["build_seconds"]), 12.5)
        self.assertEqual(rows[0]["create_sql"], result["create_sql"])
        self.assertEqual(json.loads(rows[0]["service_configuration"]), result["service_configuration"])
        self.assertEqual(json.loads(rows[0]["build_options"]), result["build_options"])
        self.assertEqual(rows[0]["expected_engine_version"], "")

    def test_csv_export_never_overwrites_existing_file(self):
        path = Path(self.temporary.name) / "existing.csv"
        path.write_text("previous result", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            build.save_csv_result(path, {"status": "succeeded"})
        self.assertEqual(path.read_text(encoding="utf-8"), "previous result")

    def test_csv_export_failure_preserves_create_and_original_exception(self):
        original = OSError("CSV disk error")
        with patch.object(build, "save_csv_result", side_effect=original), self.assertRaises(OSError) as caught:
            build.build_index(**self.args)
        self.assertIs(caught.exception, original)
        result = json.loads((self.directory / "result.json").read_text())
        self.assertEqual(result["status"], "reporting_failed")
        self.assertTrue(result["create_completed"])
        self.assertEqual(result["build_seconds"], 12.5)
        self.assertTrue((self.directory / "create-result.json").exists())
        self.assertEqual(self.create_count, 1)

    def test_invalid_maxdop_authentication_and_index_name_fail_before_output(self):
        for values in ({"maxdop": -1}, {"index_name": "bad]; DROP TABLE x"},
                       {"trusted_connection": False}, {"username": "sql_login"}, {"repetition": 0},
                       {"expected_engine_version": "latest"}, {"size": "1M"}, {"size": "1m"}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                build.build_index(**{**self.args, **values})
        self.driver.connect.assert_not_called()
        self.assertFalse(self.directory.exists())

    def test_incomplete_population_does_not_create(self):
        self.population["row_count"] = 9999999
        with self.assertRaisesRegex(ValueError, "non-null documents"):
            build.build_index(**self.args)
        self.assertEqual(self.create_count, 0)
        self.assertEqual(json.loads((self.directory / "result.json").read_text())["status"], "failed")

    def test_target_permissions_schema_and_key_fail_before_create(self):
        for attribute, field, value in (("target", "database_matches", 0), ("target", "object_id", None),
                                        ("target", "can_alter", 0), ("target", "can_select", 0),
                                        ("column", "vector_dimensions", 3), ("column", "vector_base_type", 1),
                                        ("column", "is_nullable", True), ("key", "type", 2)):
            with self.subTest(field=field), patch.dict(getattr(self, attribute), {field: value}):
                with self.assertRaises(ValueError):
                    build.build_index(**{**self.args, "output_dir": self.directory / field})
        self.assertEqual(self.create_count, 0)

    def test_existing_index_refused_by_default_without_prompt(self):
        self.existing = self.created.copy()
        with patch("builtins.input") as prompt, self.assertRaisesRegex(ValueError, "already exists"):
            build.build_index(**self.args)
        prompt.assert_not_called()
        self.assertNotIn("drop", self.events)
        self.assertEqual(self.create_count, 0)

    def test_existing_index_replacement_requires_exact_confirmation(self):
        self.existing = self.created.copy()
        with patch("builtins.input", return_value="no"), self.assertRaises(ValueError):
            build.build_index(**self.args, replace_existing=True)
        self.assertNotIn("drop", self.events)

    def test_approved_drop_is_before_the_single_timed_create(self):
        self.existing = self.created.copy()
        with patch("builtins.input", return_value="yfcc_vector_index"):
            build.build_index(**self.args, replace_existing=True)
        self.assertLess(self.events.index("drop"), self.events.index("create"))
        self.assertEqual(self.create_count, 1)
        drops = [sql for sql, params in self.calls if sql.startswith("DROP INDEX")]
        self.assertEqual(drops, ["DROP INDEX [yfcc_vector_index] ON [dbo].[yfcc_10M_documents];"])

    def test_changed_index_during_confirmation_is_not_dropped(self):
        self.existing = self.created.copy()
        self.changed_index = True
        with patch("builtins.input", return_value="yfcc_vector_index"), self.assertRaisesRegex(ValueError, "changed"):
            build.build_index(**self.args, replace_existing=True)
        self.assertNotIn("drop", self.events)

    def test_nonvector_index_is_never_replaced(self):
        self.existing["index_id"] = 1
        with patch("builtins.input") as prompt, self.assertRaisesRegex(ValueError, "not a vector index"):
            build.build_index(**self.args, replace_existing=True)
        prompt.assert_not_called()
        self.assertNotIn("drop", self.events)

    def test_failed_create_has_no_success_duration_and_is_not_retried(self):
        self.timing.update(create_completed=False, build_seconds=None)
        self.create_error = RuntimeError("original server error")
        with self.assertRaises(RuntimeError) as caught:
            build.build_index(**self.args)
        self.assertIs(caught.exception, self.create_error)
        result = json.loads((self.directory / "result.json").read_text())
        self.assertIsNone(result["build_seconds"])
        self.assertFalse(result["create_completed"])
        self.assertEqual(result["started_utc"], self.timing["started_utc"])
        self.assertEqual(result["error"], "original server error")
        self.assertEqual(self.create_count, 1)
        with (self.directory / "result.csv").open(encoding="utf-8", newline="") as source:
            row = next(csv.DictReader(source))
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["build_seconds"], "")
        self.assertEqual(row["error"], "original server error")

    def test_completed_create_survives_reporting_failure_and_can_be_recovered(self):
        self.created["on_embedding"] = False
        with self.assertRaises(ValueError):
            build.build_index(**self.args)
        result = json.loads((self.directory / "result.json").read_text())
        self.assertEqual(result["status"], "reporting_failed")
        self.assertTrue(result["create_completed"])
        self.assertEqual(result["build_seconds"], 12.5)
        recovered = build.recover_result(self.directory)
        self.assertEqual(recovered["status"], "reporting_failed")
        self.assertEqual(self.create_count, 1)
        self.driver.connect.assert_called_once()
        self.assertEqual(len(list(self.directory.glob("recovered-*.json"))), 1)
        recovered_csv = list(self.directory.glob("recovered-*.csv"))
        self.assertEqual(len(recovered_csv), 1)
        with recovered_csv[0].open(encoding="utf-8", newline="") as source:
            row = next(csv.DictReader(source))
        self.assertEqual(row["status"], "reporting_failed")
        self.assertEqual(float(row["build_seconds"]), 12.5)

    def test_interrupted_create_is_not_success_or_retried(self):
        self.timing = None
        self.create_error = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            build.build_index(**self.args)
        result = json.loads((self.directory / "result.json").read_text())
        self.assertEqual(result["status"], "interrupted")
        self.assertIsNone(result["build_seconds"])
        self.assertEqual(self.create_count, 1)

    def test_zero_maxdop_and_one_hidden_password_prompt(self):
        with patch.object(build.getpass, "getpass", return_value="test-only};secret") as prompt:
            result = build.build_index(**{**self.args, "trusted_connection": False, "username": "sql_login", "maxdop": 0})
        self.assertEqual(result["maxdop"], 0)
        prompt.assert_called_once()
        connection_string = self.driver.connect.call_args.args[0]
        self.assertIn("UID={sql_login}", connection_string)
        self.assertIn("PWD={test-only}};secret}", connection_string)
        self.assertNotIn("Trusted_Connection", connection_string)
        for path in self.directory.iterdir():
            self.assertNotIn("test-only", path.read_text())

    def test_values_are_bound_and_tls_override_is_only_explicit(self):
        database = "Vector ';[]};Database"
        build.build_index(**{**self.args, "database": database, "trust_server_certificate": True})
        self.assertIn("TrustServerCertificate={yes}", self.driver.connect.call_args.args[0])
        self.assertIn("DATABASE={Vector ';[]}};Database}", self.driver.connect.call_args.args[0])
        for sql, parameters in self.calls:
            self.assertNotIn(database, sql)
            if "AS database_matches" in sql:
                self.assertEqual(parameters[0], database)
            if "FROM (SELECT OBJECT_ID" in sql:
                self.assertEqual(parameters, ("[dbo].[yfcc_10M_documents]", "yfcc_vector_index"))

    def test_engine_version_is_recorded_without_implicit_pin(self):
        self.metadata["engine_version"] = "18.0.999.0"
        result = build.build_index(**self.args)
        self.assertEqual(result["engine_version"], "18.0.999.0")
        self.assertIsNone(result["expected_engine_version"])

    def test_explicit_engine_pin_stops_mismatched_build(self):
        with self.assertRaisesRegex(ValueError, "pin"):
            build.build_index(**self.args, expected_engine_version="18.0.999.0")
        self.assertEqual(self.create_count, 0)

    def test_sql_timer_boundary_excludes_population_drop_and_postchecks(self):
        script = (build.ROOT / "scripts/build-index.sql").read_text()
        start = script.index("SET @started = SYSUTCDATETIME();")
        finish = script.index("SET @finished = SYSUTCDATETIME();")
        self.assertEqual(script[start:finish].splitlines(), [
            "SET @started = SYSUTCDATETIME();", "    EXEC sys.sp_executesql @create_sql;", "    "])
        self.assertIn("DATEDIFF_BIG(NANOSECOND, @started, @finished)", script)
        self.assertNotIn("DROP", script)
        self.assertNotIn("COUNT_BIG", script)
        for forbidden in ("$(", "JSON_MODIFY", "VECTOR_BUILD_RESULT", "Phase"):
            self.assertNotIn(forbidden, script)
        self.assertIn("DECLARE @create_sql NVARCHAR(MAX) = ?;", script)
        self.assertLess(len(script.splitlines()), 25)

    def test_schema_queries_avoid_vector_type_name_and_database_id_heuristics(self):
        build.build_index(**self.args)
        statements = "\n".join(sql for sql, parameters in self.calls)
        self.assertNotIn("TYPE_NAME", statements)
        self.assertNotIn("DB_ID() <=", statements)
        self.assertIn("vector_dimensions", statements)
        self.assertIn("vector_base_type", statements)

    def test_dispatcher_routes_build_script_and_exit_code(self):
        with patch.object(benchmark.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)) as run:
            self.assertEqual(benchmark.main(["build", "--size", "10M", "--maxdop", "0"]), 1)
        command = run.call_args.args[0]
        self.assertEqual(Path(command[1]), build.ROOT / "build.py")
        self.assertEqual(command[2:], ["--size", "10M", "--maxdop", "0"])

    def test_export_failure_keeps_completion_checkpoint_and_original_error(self):
        original = build.save_result
        export_error = OSError("disk error")
        def fail_final_export(path, result):
            if path.name == "result.json":
                raise export_error
            original(path, result)
        with patch.object(build, "save_result", side_effect=fail_final_export), self.assertRaises(OSError) as caught:
            build.build_index(**self.args)
        self.assertIs(caught.exception, export_error)
        recovered = build.recover_result(self.directory)
        self.assertEqual(recovered["status"], "reporting_incomplete")
        self.assertEqual(recovered["build_seconds"], 12.5)
        self.assertTrue((self.directory / "create-result.json").exists())
        self.assertEqual(self.create_count, 1)

    def test_failure_export_and_connection_cleanup_do_not_mask_sql_error(self):
        original = build.save_result
        def fail_result(path, result):
            if path.name == "result.json":
                raise OSError("export also failed")
            original(path, result)
        self.timing.update(create_completed=False, build_seconds=None)
        self.create_error = RuntimeError("original SQL failure")
        self.connection.close.side_effect = OSError("close also failed")
        with patch.object(build, "save_result", side_effect=fail_result), self.assertRaises(RuntimeError) as caught:
            build.build_index(**self.args)
        self.assertIs(caught.exception, self.create_error)
        self.assertTrue((self.directory / "request.json").exists())

    def test_late_error_after_completion_retains_completed_state(self):
        self.create_error = RuntimeError("late SQL error")
        with self.assertRaises(RuntimeError) as caught:
            build.build_index(**self.args)
        self.assertIs(caught.exception, self.create_error)
        result = json.loads((self.directory / "result.json").read_text())
        self.assertTrue(result["create_completed"])
        self.assertEqual(result["status"], "reporting_failed")
        self.assertEqual(self.create_count, 1)

    def test_connect_error_redacts_password_but_rethrows_original(self):
        original = RuntimeError("Driver error with PWD={test-only}};secret}")
        self.driver.connect.side_effect = original
        with patch.object(build.getpass, "getpass", return_value="test-only};secret"), self.assertRaises(RuntimeError) as caught:
            build.build_index(**{**self.args, "trusted_connection": False, "username": "sql_login"})
        self.assertIs(caught.exception, original)
        for path in self.directory.iterdir():
            self.assertNotIn("test-only", path.read_text())
        self.assertIn("[redacted]", (self.directory / "result.json").read_text())

    def test_missing_completion_and_negative_time_are_not_success(self):
        for timing in (None, dict(self.timing, build_seconds=-1)):
            with self.subTest(timing=timing):
                self.timing = timing
                self.create_count = 0
                with self.assertRaises((ValueError, RuntimeError)):
                    build.build_index(**{**self.args, "output_dir": self.directory / str(timing is None)})
                self.assertEqual(self.create_count, 1)


class ExecuteTests(unittest.TestCase):
    def test_consumes_all_result_sets_and_binds_values(self):
        cursor = Mock()
        connection = Mock()
        connection.cursor.return_value = cursor
        type(cursor).description = PropertyMock(side_effect=[None, [("value",)], [("other",)]])
        cursor.fetchall.side_effect = [[(1,)], [(2,)]]
        cursor.nextset.side_effect = [True, True, False]
        self.assertEqual(build.execute_and_consume(connection, "SELECT ?", ("bound value",)),
                         [[{"value": 1}], [{"other": 2}]])
        cursor.execute.assert_called_once_with("SELECT ?", "bound value")
        self.assertEqual(cursor.nextset.call_count, 3)
        cursor.close.assert_called_once()

    def test_late_sql_error_preserves_results_and_original_exception(self):
        cursor = Mock()
        connection = Mock()
        connection.cursor.return_value = cursor
        cursor.description = [("create_completed",)]
        cursor.fetchall.return_value = [(True,)]
        original = RuntimeError("late SQL error")
        cursor.nextset.side_effect = original
        cursor.close.side_effect = OSError("cleanup failed too")
        results = []
        with self.assertRaises(RuntimeError) as caught:
            build.execute_and_consume(connection, "batch", results=results)
        self.assertIs(caught.exception, original)
        self.assertEqual(results, [[{"create_completed": True}]])
        cursor.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()