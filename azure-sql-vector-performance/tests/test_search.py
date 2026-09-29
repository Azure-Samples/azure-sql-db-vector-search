from copy import deepcopy
from contextlib import redirect_stdout
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
import uuid
import xml.etree.ElementTree as ET


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import search
import benchmark


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.run_id = uuid.UUID("00112233-4455-6677-8899-aabbccddeeff")
        self.counters = dict(dropped_event_count=0, dropped_buffer_count=0,
                             largest_event_dropped_size=0, pending_buffers=0)
        self.root = ET.Element("RingBufferTarget", truncated="0", droppedCount="0", eventCount="2", totalEventsProcessed="2")
        for query_id, duration in ((1, 3000), (0, 1000)):
            event = ET.SubElement(self.root, "event", name="sql_statement_completed")
            for kind, name, value in (
                ("data", "statement", f"SELECT /*vector-latency:{self.run_id.hex}*/ @sink = id"),
                ("data", "duration", str(duration)), ("data", "physical_reads", "0"),
                ("action", "session_id", "51"),
                ("action", "context_info", "0x" + (self.run_id.bytes + query_id.to_bytes(4, "big") + b"\x01").hex()),
            ):
                ET.SubElement(ET.SubElement(event, kind, name=name), "value").text = value

    def parse(self, root=None):
        return search.parse_events(ET.tostring(self.root if root is None else root, encoding="unicode"),
                                   self.run_id, 51, 2, self.counters)

    def test_stamp_matches_sql_big_endian_int_and_opaque_uuid_bytes(self):
        value = "0x" + (self.run_id.bytes + (258).to_bytes(4, "big") + b"\x02").hex()
        self.assertEqual(search.decode_stamp(value), (self.run_id, 258, 2))
        self.assertEqual(search.decode_stamp(value + "00" * 107), (self.run_id, 258, 2))
        for malformed in (value[:-2], value[:-2] + "03", value + "01"):
            with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                search.decode_stamp(malformed)

    def test_event_order_is_not_query_order(self):
        result = self.parse()
        self.assertEqual(result[0]["latency_us"], 1000)
        self.assertEqual(result[1]["latency_us"], 3000)
        self.assertIsNone(result[0]["page_server_reads"])

    def test_short_and_empty_answers_keep_k_denominator_and_ms_conversion(self):
        rows = [dict(query_id=0, returned=3, matched=3, ground_truth_count=10, latency_us=None),
                dict(query_id=1, returned=0, matched=0, ground_truth_count=10, latency_us=None)]
        result = search.attach_durations(rows, self.parse(), self.run_id, 1, 10, False)
        self.assertEqual(result[0]["recall"], 0.3)
        summary = search.summarize(result, 10)
        self.assertEqual(summary["mean_recall"], 0.15)
        self.assertEqual(summary["returned_lt_k_percent"], 100)
        self.assertEqual(summary["p50_ms"], 2)
        self.assertEqual(summary["p95_ms"], 2.9)

    def test_hyperscale_missing_remote_counter_is_unknown_and_reads_are_retained(self):
        durations = self.parse()
        durations[1].update(physical_reads=1, page_server_reads=2)
        rows = [dict(query_id=query_id, returned=10, matched=9, ground_truth_count=10, latency_us=None)
                for query_id in range(2)]
        measured = search.attach_durations(rows, durations, self.run_id, 1, 10, True)
        self.assertIsNone(measured[0]["hot"])
        self.assertFalse(measured[1]["hot"])
        self.assertEqual(search.summarize(measured, 10)["read_bearing_count"], 1)
        self.assertEqual(len(measured), 2)

    def test_truncation_overwrite_and_dropped_events_are_rejected(self):
        for name in ("truncated", "droppedCount", "totalEventsProcessed", "eventCount"):
            root = deepcopy(self.root)
            root.set(name, "1" if name in ("truncated", "droppedCount") else "3")
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.parse(root)
        for name in self.counters:
            with self.subTest(name=name):
                self.counters[name] = 1
                with self.assertRaises(ValueError):
                    self.parse()
                self.counters[name] = 0

    def test_missing_duplicate_and_invalid_duration_fail(self):
        for value in (None, "-1", "not a number"):
            root = deepcopy(self.root)
            root[0].find("data[@name='duration']/value").text = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.parse(root)
        root = deepcopy(self.root)
        root[0].find("action[@name='context_info']/value").text = root[1].findtext("action[@name='context_info']/value")
        root[0].set("name", "sp_statement_completed")
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.parse(root)

    def test_zero_duration_is_valid_but_absent_evidence_and_rows_are_not(self):
        self.root[0].find("data[@name='duration']/value").text = "0"
        self.assertEqual(self.parse()[1]["latency_us"], 0)
        self.root.remove(self.root[0])
        self.root.set("eventCount", "1")
        self.root.set("totalEventsProcessed", "1")
        with self.assertRaisesRegex(ValueError, "found 1"):
            self.parse()
        for rows in ([], [dict(query_id=0, returned=0, matched=0, ground_truth_count=0, latency_us=None)],
                     [dict(query_id=0, returned=3, matched=4, ground_truth_count=10, latency_us=None)]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                search.validate_rows(rows, 1, 10)

    def test_batch_sql_text_is_not_used_to_match_timing_statement(self):
        self.root[0].find("data[@name='statement']/value").text = "INSERT INTO @found SELECT id"
        ET.SubElement(ET.SubElement(self.root[0], "action", name="sql_text"), "value").text = f"/*vector-latency:{self.run_id.hex}*/"
        with self.assertRaisesRegex(ValueError, "found 1"):
            self.parse()

    def test_wrong_session_run_and_execution_kind_are_rejected(self):
        for field, value in (("session_id", "52"), ("context_info", "0x" + "00" * 20 + "01"),
                             ("context_info", "0x" + self.run_id.hex + "0000000102")):
            root = deepcopy(self.root)
            root[0].find(f"action[@name='{field}']/value").text = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.parse(root)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name).resolve() / "repetition"
        self.connection = object()
        self.settings = dict(xe_scope="SERVER", size="10M", k=10, query_count=2,
                             session_id=51, requires_page_server_reads=False)
        self.columns = [{"object_name": name, "name": field, "description": "Elapsed time in microseconds"}
                        for name in search.EVENT_NAMES for field in ("statement", "duration", "collect_statement")]
        self.calls = []
        self.fail_workload = False
        self.fail_evidence = False
        self.rows = [dict(query_id=0, returned=3, matched=3, ground_truth_count=10, latency_us=None),
                     dict(query_id=1, returned=0, matched=0, ground_truth_count=10, latency_us=None)]
        self.run_id = uuid.UUID("00112233-4455-6677-8899-aabbccddeeff")

    def execute(self, connection, sql, parameters=(), results=None):
        self.assertIs(connection, self.connection)
        self.calls.append(sql)
        if "WHILE @query_id" in sql:
            results.append(self.rows)
            if self.fail_workload:
                raise RuntimeError("later result-set error")
            return results
        if "targets.target_data" in sql:
            if self.fail_evidence:
                raise RuntimeError("cannot read evidence")
            fixture = EvidenceTests()
            fixture.setUp()
            return [[{"target_data": ET.tostring(fixture.root, encoding="unicode")}]]
        if "SELECT dropped_event_count" in sql:
            return [[dict(dropped_event_count=0, dropped_buffer_count=0,
                          largest_event_dropped_size=0, pending_buffers=0)]]
        if "STATE = STOP" in sql:
            self.assertTrue((self.directory / "events.xml").is_file())
            self.assertTrue((self.directory / "event-counters.json").is_file())
        return []

    def run_repetition(self, repetition=1):
        with patch.object(search, "execute_and_consume", side_effect=self.execute), patch.object(search.uuid, "uuid4", return_value=self.run_id):
            return search.run_repetition(self.connection, self.settings, self.columns, self.directory, repetition)

    def test_collection_starts_before_one_loop_and_evidence_is_saved_before_stop(self):
        result = self.run_repetition()
        self.assertEqual(result["status"], "succeeded")
        workload_calls = [sql for sql in self.calls if "WHILE @query_id" in sql]
        self.assertEqual(len(workload_calls), 1)
        self.assertIn("STATE = START", self.calls[1])
        self.assertIn("WHILE @query_id", self.calls[2])
        self.assertIn("targets.target_data", self.calls[3])
        self.assertIn("STATE = STOP", self.calls[-2])
        self.assertIn("DROP EVENT SESSION", self.calls[-1])
        self.assertEqual(result["summary"]["mean_recall"], 0.15)
        ddl = (self.directory / "collection.sql").read_text()
        self.assertIn("([statement],", ddl)
        self.assertNotIn("sql_text", ddl)

    def test_csv_contains_each_measured_query_with_latency_and_recall(self):
        self.run_repetition()
        with (self.directory / "queries.csv").open(encoding="utf-8", newline="") as source:
            reader = csv.DictReader(source)
            self.assertEqual(reader.fieldnames, list(search.QUERY_CSV_FIELDS))
            rows = list(reader)
        measured = json.loads((self.directory / "queries.json").read_text())
        self.assertEqual(len(rows), 2)
        for actual, expected in zip(rows, measured):
            for name, value in expected.items():
                self.assertEqual(actual[name], "" if value is None else str(value))
            self.assertEqual(float(actual["latency_ms"]), expected["latency_us"] / 1000.0)
        self.assertEqual(rows[0]["recall"], "0.3")
        self.assertEqual(rows[1]["returned"], "0")
        self.assertEqual(rows[1]["recall"], "0.0")
        self.assertEqual(rows[0]["physical_reads"], "0")
        self.assertEqual(rows[0]["page_server_reads"], "")

    def test_csv_export_failure_retains_json_and_evidence_without_replay(self):
        with patch.object(search, "write_query_csv", side_effect=OSError("CSV disk error")):
            with self.assertRaises(RuntimeError):
                self.run_repetition()
        self.assertEqual(sum("WHILE @query_id" in sql for sql in self.calls), 1)
        self.assertTrue((self.directory / "queries.json").exists())
        self.assertTrue((self.directory / "events.xml").exists())
        result = json.loads((self.directory / "result.json").read_text())
        self.assertEqual(result["status"], "failed")
        self.assertIn("CSV disk error", result["validation_error"])
        self.assertNotIn("summary", result)

    def test_warmup_is_one_discarded_loop_without_events_or_latency(self):
        result = self.run_repetition(0)
        self.assertEqual(result["status"], "warmup_discarded")
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn("summary", result)
        self.assertFalse((self.directory / "queries.json").exists())
        self.assertFalse((self.directory / "queries.csv").exists())

    def test_failed_query_is_not_an_empty_answer_and_is_not_replayed(self):
        self.fail_workload = True
        with self.assertRaises(RuntimeError):
            self.run_repetition()
        self.assertEqual(sum("WHILE @query_id" in sql for sql in self.calls), 1)
        self.assertTrue((self.directory / "raw-result-sets.json").exists())
        self.assertTrue((self.directory / "events.xml").exists())
        self.assertFalse((self.directory / "queries.json").exists())
        self.assertFalse((self.directory / "queries.csv").exists())
        result = json.loads((self.directory / "result.json").read_text())
        self.assertEqual(result["status"], "failed")
        self.assertIn("later result-set error", result["error"])

    def test_collection_is_retained_if_evidence_cannot_be_preserved(self):
        self.fail_evidence = True
        with self.assertRaises(RuntimeError):
            self.run_repetition()
        self.assertFalse(any("STATE = STOP" in sql or "DROP EVENT SESSION" in sql for sql in self.calls))
        result = json.loads((self.directory / "result.json").read_text())
        self.assertTrue(result["collection_retained"])

    def test_existing_repetition_is_not_overwritten(self):
        self.directory.mkdir()
        with self.assertRaises(FileExistsError):
            self.run_repetition()
        self.assertEqual(self.calls, [])

    def test_metadata_requires_both_statement_events_and_microsecond_units(self):
        search.validate_event_metadata(self.columns)
        for columns in (self.columns[:3], [{**column, "description": "milliseconds"} for column in self.columns]):
            with self.assertRaises(ValueError):
                search.validate_event_metadata(columns)

    def test_workload_pairs_searches_and_saves_rowcounts_immediately(self):
        sql = search.render_workload("10M", 10, 2, self.run_id)
        self.assertEqual(sql.count("/*vector-latency:"), 1)
        self.assertEqual(sql.count("WITH (FORCE_ANN_ONLY)"), 2)
        self.assertEqual(sql.count("OPTION (MAXDOP 1);"), 2)
        self.assertIn("OPTION (MAXDOP 1);\n        SET @timing_returned = @@ROWCOUNT;", sql)
        self.assertIn("OPTION (MAXDOP 1);\n        SET @returned = @@ROWCOUNT;", sql)
        self.assertLess(sql.index("+ 0x01"), sql.index("@sink = neighbors.id"))
        self.assertLess(sql.index("SET @timing_returned"), sql.index("+ 0x02"))
        self.assertLess(sql.index("INSERT INTO @found"), sql.index("SET @query_id += 1"))
        self.assertNotIn("CREATE INDEX", sql)
        self.assertNotIn("CREATE VECTOR INDEX", sql)
        self.assertNotIn("__SIZE__", sql)

    def test_preflight_checks_vector_metadata_not_underlying_storage_name(self):
        sql = (search.ROOT / "scripts/validate-search.sql").read_text(encoding="utf-8")
        self.assertIn("vector_dimensions = 1280", sql)
        self.assertIn("vector_base_type = 0", sql)
        self.assertNotIn("TYPE_NAME(system_type_id)", sql)

    def test_all_result_sets_are_drained_and_late_errors_surface(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.description = [("query_id",)]
        cursor.fetchmany.side_effect = [[(0,), (1,)], [], [(2,)], []]
        cursor.nextset.side_effect = [True, RuntimeError("late failure")]
        results = []
        with self.assertRaisesRegex(RuntimeError, "late failure"):
            search.execute_and_consume(connection, "SELECT workload", results=results)
        self.assertEqual(results, [[{"query_id": 0}, {"query_id": 1}], [{"query_id": 2}]])
        cursor.close.assert_called_once()

    def test_cursor_close_does_not_hide_the_workload_error(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.execute.side_effect = RuntimeError("original workload failure")
        cursor.close.side_effect = RuntimeError("cursor cleanup failure")
        with self.assertRaisesRegex(RuntimeError, "original workload failure"):
            search.execute_and_consume(connection, "SELECT workload")


class CsvTests(unittest.TestCase):
    def test_csv_preserves_unknowns_zero_latency_and_quoted_values(self):
        row = dict(run_id="run,with\"quotes", repetition=1, query_id=0, returned=0, matched=0,
                   ground_truth_count=10, latency_us=0, recall=0.0, physical_reads=None,
                   page_server_reads=None, hot=None, event_name="sql_statement_completed")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "queries.csv"
            search.write_query_csv(path, [row])
            with path.open(encoding="utf-8", newline="") as source:
                rows = list(csv.DictReader(source))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["run_id"], row["run_id"])
        self.assertEqual(rows[0]["latency_us"], "0")
        self.assertEqual(rows[0]["latency_ms"], "0.0")
        for name in ("physical_reads", "page_server_reads", "hot"):
            self.assertEqual(rows[0][name], "")
        self.assertNotIn("latency_ms", row)

    def test_existing_csv_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "queries.csv"
            path.write_text("existing results", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                search.write_query_csv(path, [])
            self.assertEqual(path.read_text(encoding="utf-8"), "existing results")


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name).resolve()
        dataset = root / "yfcc-images-10M"
        dataset.mkdir()
        self.manifest = dict(dataset="yfcc-images-10M", document_count=10000000, dimensions=1280,
                             metric="euclidean", vector_dtype="float32", ground_truth_k=100, query_count=100000)
        self.manifest_path = dataset / "manifest.json"
        self.manifest_path.write_text(json.dumps(self.manifest))
        self.args = SimpleNamespace(size="10M", server="localhost,1433", database="Vector Test",
                                    expected_engine_version="18.0.251.0", output_dir=root / "attempt",
                                    data_dir=root, k=10, query_count=2, repetitions=10, maxdop=1,
                                    index_name="yfcc_vector_index", dimension=1280, metric="euclidean",
                                    query_mode="ann", username=None, trusted_connection=True,
                                    trust_server_certificate=True)

    def test_same_connection_one_warmup_then_ten_passes(self):
        connection = MagicMock()
        state = dict(status="succeeded", summary={})
        with patch.object(search, "connect", return_value=connection), \
                patch.object(search, "preflight", return_value=({}, [])), \
                patch.object(search, "run_repetition", return_value=state) as run, redirect_stdout(io.StringIO()):
            result = search.run_search(self.args)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual([call.args[-1] for call in run.call_args_list], list(range(11)))
        self.assertTrue(all(call.args[0] is connection for call in run.call_args_list))
        connection.close.assert_called_once()
        settings = json.loads((self.args.output_dir / "settings.json").read_text())
        self.assertEqual(settings["maxdop"], 1)
        self.assertEqual(settings["repetitions"], 10)
        self.assertNotIn("username", settings)

    def test_query_count_limit_rejects_before_files_connection_or_workload(self):
        with patch.object(search, "connect") as connect, patch.object(Path, "read_text") as read, \
                patch.object(search, "run_repetition") as run:
            for query_count in (-1, 0, 1001, 100000):
                with self.subTest(query_count=query_count):
                    self.args.query_count = query_count
                    with self.assertRaisesRegex(ValueError, r"1\.\.1000.*ring-buffer"):
                        search.run_search(self.args)
                    with self.assertRaises(ValueError):
                        search.render_workload("10M", 10, query_count, uuid.uuid4())
            connect.assert_not_called()
            read.assert_not_called()
            run.assert_not_called()
        self.assertFalse(self.args.output_dir.exists())

    def test_query_count_boundaries_are_supported(self):
        for query_count in (1, 1000):
            with self.subTest(query_count=query_count):
                self.args.query_count = query_count
                self.args.output_dir = self.args.output_dir.parent / f"queries-{query_count}"
                connection = MagicMock()
                with patch.object(search, "connect", return_value=connection), \
                        patch.object(search, "preflight", return_value=({}, [])), \
                        patch.object(search, "run_repetition", return_value=dict(summary={})) as run, \
                        redirect_stdout(io.StringIO()):
                    result = search.run_search(self.args)
                self.assertEqual(result["status"], "succeeded")
                self.assertEqual(run.call_count, self.args.repetitions + 1)
                self.assertTrue(all(call.args[1]["query_count"] == query_count for call in run.call_args_list))
                self.assertNotIn("__QUERY_COUNT__", search.render_workload("10M", 10, query_count, uuid.uuid4()))
                connection.close.assert_called_once()

    def test_cli_reports_ring_buffer_limit_without_reading_manifest(self):
        arguments = ["--size", "10M", "--server", self.args.server, "--database", self.args.database,
                     "--expected-engine-version", self.args.expected_engine_version, "--trusted-connection",
                     "--output-dir", str(self.args.output_dir), "--query-count", "100000"]
        with patch.object(search, "connect") as connect, patch.object(Path, "read_text") as read, \
                patch.object(search.sys, "stderr", io.StringIO()) as errors:
            self.assertEqual(search.main(arguments), 1)
            self.assertIn("1..1000", errors.getvalue())
            self.assertIn("ring-buffer collector", errors.getvalue())
            connect.assert_not_called()
            read.assert_not_called()
        self.assertFalse(self.args.output_dir.exists())
        with redirect_stdout(io.StringIO()) as help_output, self.assertRaises(SystemExit) as caught:
            search.main(["--help"])
        self.assertEqual(caught.exception.code, 0)
        self.assertIn("1..1000", help_output.getvalue())

    def test_failed_pass_stops_remaining_repetitions_and_retains_attempt(self):
        connection = MagicMock()
        with patch.object(search, "connect", return_value=connection), \
                patch.object(search, "preflight", return_value=({}, [])), \
                patch.object(search, "run_repetition", side_effect=[{}, RuntimeError("evidence lost")]) as run, \
                redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
            search.run_search(self.args)
        self.assertEqual(run.call_count, 2)
        connection.close.assert_called_once()
        self.assertEqual(json.loads((self.args.output_dir / "result.json").read_text())["status"], "failed")

    def test_existing_output_or_manifest_mismatch_does_not_connect(self):
        with patch.object(search, "connect") as connect:
            for field, value in (("metric", "cosine"), ("dimensions", 3), ("document_count", 50000),
                                 ("ground_truth_k", 5), ("query_count", 1)):
                with self.subTest(field=field):
                    self.manifest_path.write_text(json.dumps({**self.manifest, field: value}))
                    with self.assertRaises(ValueError):
                        search.run_search(self.args)
            self.manifest_path.write_text(json.dumps(self.manifest))
            self.args.output_dir.mkdir()
            with self.assertRaises(FileExistsError):
                search.run_search(self.args)
            connect.assert_not_called()

    def test_removed_1m_is_rejected_before_manifest_or_connection(self):
        with patch.object(search, "connect") as connect, patch.object(Path, "read_text") as read:
            for size in ("1M", "1m"):
                with self.subTest(size=size):
                    self.args.size = size
                    with self.assertRaisesRegex(ValueError, "supported"):
                        search.run_search(self.args)
                    with self.assertRaises(ValueError):
                        search.render_workload(size, 10, 2, uuid.uuid4())
            connect.assert_not_called()
            read.assert_not_called()
        self.assertFalse(self.args.output_dir.exists())

    def test_target_observation_is_saved_before_version_mismatch(self):
        self.args.output_dir.mkdir()
        target = dict(session_id=51, database_name="Vector Test", engine_version="18.0.999.0")
        with patch.object(search, "execute_and_consume", return_value=[[target]]) as execute:
            with self.assertRaisesRegex(ValueError, "target"):
                search.preflight(object(), self.args, self.args.output_dir)
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(json.loads((self.args.output_dir / "target-observed.json").read_text()), target)

    def test_windows_connection_is_dedicated_autocommit_and_reconnect_disabled(self):
        import pyodbc
        with patch.object(pyodbc, "drivers", return_value=["ODBC Driver 18 for SQL Server"]), \
                patch.object(pyodbc, "connect") as connect, patch.object(search.getpass, "getpass") as prompt:
            search.connect(self.args)
        self.assertFalse(pyodbc.pooling)
        self.assertTrue(connect.call_args.kwargs["autocommit"])
        self.assertIn("Trusted_Connection={yes}", connect.call_args.args[0])
        self.assertIn("ConnectRetryCount={0}", connect.call_args.args[0])
        self.assertNotIn("PWD=", connect.call_args.args[0])
        prompt.assert_not_called()

    def test_sql_password_is_prompted_and_connection_errors_do_not_expose_it(self):
        import pyodbc
        self.args.trusted_connection = False
        self.args.username = "benchmark_user"
        with patch.object(pyodbc, "drivers", return_value=["ODBC Driver 18 for SQL Server"]), \
                patch.object(pyodbc, "connect", side_effect=pyodbc.Error("28000", "test-secret")), \
                patch.object(search.getpass, "getpass", return_value="test-secret") as prompt:
            with self.assertRaises(RuntimeError) as caught:
                search.connect(self.args)
        self.assertNotIn("test-secret", str(caught.exception))
        self.assertIn("28000", str(caught.exception))
        prompt.assert_called_once()

    def test_dispatcher_forwards_search(self):
        with patch.object(benchmark.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)) as run:
            self.assertEqual(benchmark.main(["search", "--query-count", "10"]), 1)
        self.assertEqual(Path(run.call_args.args[0][1]), search.ROOT / "search.py")
        self.assertEqual(run.call_args.args[0][2:], ["--query-count", "10"])


if __name__ == "__main__":
    unittest.main()