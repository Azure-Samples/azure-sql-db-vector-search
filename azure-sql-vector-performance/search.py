import argparse
import csv
from datetime import datetime, timezone
import getpass
import json
from pathlib import Path
import sys
import uuid
import warnings
import xml.etree.ElementTree as ET

from download import DEFAULT_DATA_DIR, SIZES


ROOT = Path(__file__).resolve().parent
EVENT_NAMES = ("sql_statement_completed", "sp_statement_completed")
MAX_QUERY_COUNT = 1000
QUERY_CSV_FIELDS = (
    "run_id", "repetition", "query_id", "returned", "matched", "ground_truth_count",
    "latency_us", "latency_ms", "recall", "physical_reads", "page_server_reads", "hot", "event_name",
)


def execute_and_consume(connection, sql, parameters=(), results=None):
    if results is None:
        results = []
    cursor = connection.cursor()
    try:
        cursor.execute(sql, *parameters)
        while True:
            if cursor.description:
                columns = [column[0] for column in cursor.description]
                rows = []
                results.append(rows)
                while batch := cursor.fetchmany(256):
                    rows.extend(dict(zip(columns, row)) for row in batch)
            if not cursor.nextset():
                return results
    finally:
        original_error = sys.exc_info()[1]
        try:
            cursor.close()
        except Exception:
            if original_error is None:
                raise


def write_json(path, value):
    with path.open("x", encoding="utf-8") as output:
        json.dump(value, output, indent=2, allow_nan=False)
        output.write("\n")


def write_query_csv(path, rows):
    with path.open("x", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=QUERY_CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "latency_ms": row["latency_us"] / 1000.0})


def render_workload(size, k, query_count, run_id):
    if size not in SIZES or not 1 <= k <= SIZES[size] or not 1 <= query_count <= MAX_QUERY_COUNT:
        raise ValueError("Invalid dataset, k, or query count.")
    sql = (ROOT / "scripts/vector-search.sql").read_text(encoding="utf-8")
    for token, value in (("SIZE", size), ("K", k), ("QUERY_COUNT", query_count), ("RUN_HEX", run_id.hex)):
        sql = sql.replace(f"__{token}__", str(value))
    return sql


def decode_stamp(value):
    stamp = bytes.fromhex(value.removeprefix("0x").removeprefix("0X"))
    if len(stamp) == 128 and not any(stamp[21:]):
        stamp = stamp[:21]
    if len(stamp) != 21 or stamp[20] not in (1, 2):
        raise ValueError("Invalid CONTEXT_INFO stamp; expected run ID, query ID, and execution kind.")
    return uuid.UUID(bytes=stamp[:16]), int.from_bytes(stamp[16:20], "big", signed=True), stamp[20]


def parse_events(xml_text, run_id, session_id, query_count, counters):
    root = ET.fromstring(xml_text)
    if root.tag != "RingBufferTarget":
        raise ValueError("Expected ring-buffer XML.")
    for name in ("dropped_event_count", "dropped_buffer_count", "largest_event_dropped_size", "pending_buffers"):
        if counters.get(name) != 0:
            raise ValueError(f"Missing or nonzero XEvent counter: {name}.")
    for name in ("truncated", "droppedCount"):
        if root.get(name) != "0":
            raise ValueError(f"Missing or nonzero ring-buffer {name}.")
    events = root.findall("event")
    if int(root.attrib["eventCount"]) != len(events) or int(root.attrib["totalEventsProcessed"]) != len(events):
        raise ValueError("Ring-buffer events were overwritten or omitted.")
    marker = f"/*vector-latency:{run_id.hex}*/"
    durations = {}
    for event in events:
        statement = event.findtext("data[@name='statement']/value", "")
        if marker not in statement:
            continue
        if event.get("name") not in EVENT_NAMES:
            raise ValueError("Unexpected timing event type.")
        if event.findtext("action[@name='session_id']/value") != str(session_id):
            raise ValueError("Timing event belongs to another workload session.")
        stamp = event.findtext("action[@name='context_info']/value")
        if stamp is None:
            raise ValueError("Timing event has no CONTEXT_INFO.")
        stamped_run, query_id, kind = decode_stamp(stamp)
        if stamped_run != run_id or kind != 1 or not 0 <= query_id < query_count:
            raise ValueError("Timing marker and CONTEXT_INFO attribution disagree.")
        if query_id in durations:
            raise ValueError(f"Duplicate timing event for query {query_id}.")
        values = {}
        for name in ("duration", "physical_reads", "page_server_reads"):
            text = event.findtext(f"data[@name='{name}']/value")
            if text is None and name != "duration":
                values[name] = None
            elif text is None or not text.isdecimal():
                raise ValueError(f"Missing or invalid timing event {name} for query {query_id}.")
            else:
                values[name] = int(text)
        durations[query_id] = {"latency_us": values["duration"], "physical_reads": values["physical_reads"],
                               "page_server_reads": values["page_server_reads"], "event_name": event.get("name")}
    if set(durations) != set(range(query_count)):
        raise ValueError(f"Expected exactly {query_count} timing events; found {len(durations)}.")
    return durations


def validate_rows(rows, query_count, k):
    if len(rows) != query_count or {row["query_id"] for row in rows} != set(range(query_count)):
        raise ValueError("Result rows must cover the selected query IDs exactly once.")
    for row in rows:
        returned, matched, truth = row["returned"], row["matched"], row["ground_truth_count"]
        if truth != k or not 0 <= matched <= returned <= k or row["latency_us"] is not None:
            raise ValueError("Invalid returned/recall counts or prepopulated latency.")


def attach_durations(rows, durations, run_id, repetition, k, hyperscale):
    validate_rows(rows, len(durations), k)
    if set(durations) != set(range(len(rows))):
        raise ValueError("Timing events do not cover the selected query IDs exactly once.")
    result = []
    for row in rows:
        measured = durations[row["query_id"]]
        physical, remote = measured["physical_reads"], measured["page_server_reads"]
        hot = None if physical is None or (hyperscale and remote is None) else physical == 0 and (not hyperscale or remote == 0)
        result.append({**row, **measured, "run_id": str(run_id), "repetition": repetition,
                       "recall": row["matched"] / row["ground_truth_count"], "hot": hot})
    return result


def percentile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def summarize(rows, k):
    if not rows:
        raise ValueError("Cannot summarize an empty or failed repetition.")
    short = sum(row["returned"] < k for row in rows)
    durations = [row["latency_us"] for row in rows]
    return {
        "query_count": len(rows), "mean_recall": sum(row["recall"] for row in rows) / len(rows),
        "p50_ms": percentile(durations, 0.5) / 1000.0, "p95_ms": percentile(durations, 0.95) / 1000.0,
        "percentile_method": "linear interpolation at (n - 1) * p (type 7)",
        "returned_lt_k_count": short, "returned_lt_k_percent": short * 100.0 / len(rows),
        "hot_count": sum(row["hot"] is True for row in rows),
        "read_bearing_count": sum((row["physical_reads"] or 0) > 0 or (row["page_server_reads"] or 0) > 0 for row in rows),
        "hot_unknown_count": sum(row["hot"] is None for row in rows),
    }


def validate_event_metadata(columns):
    for event_name in EVENT_NAMES:
        fields = {column["name"]: column for column in columns if column["object_name"] == event_name}
        if "statement" not in fields or "duration" not in fields:
            raise ValueError(f"{event_name} must expose its own statement and duration fields.")
        if "microsecond" not in (fields["duration"]["description"] or "").lower():
            raise ValueError(f"Cannot establish microsecond duration units for {event_name} from target metadata.")


def event_session_sql(name, scope, session_id, run_id, query_count, columns):
    events = []
    for event_name in EVENT_NAMES:
        collect = "SET collect_statement = (1) " if any(
            column["object_name"] == event_name and column["name"] == "collect_statement" for column in columns) else ""
        events.append(
            f"ADD EVENT sqlserver.{event_name} ({collect}"
            "ACTION(sqlserver.context_info, sqlserver.session_id) "
            f"WHERE ([sqlserver].[session_id] = ({session_id}) AND "
            f"[sqlserver].[like_i_sql_unicode_string]([statement], N'%/*vector-latency:{run_id.hex}*/%')))"
        )
    return (f"CREATE EVENT SESSION [{name}] ON {scope}\n" + ",\n".join(events)
            + f"\nADD TARGET package0.ring_buffer(SET MAX_MEMORY = 4096, MAX_EVENTS_LIMIT = {query_count * 2 + 16})"
            + "\nWITH (MAX_MEMORY = 4096 KB, EVENT_RETENTION_MODE = ALLOW_SINGLE_EVENT_LOSS, "
              "MAX_DISPATCH_LATENCY = 1 SECONDS, TRACK_CAUSALITY = OFF, STARTUP_STATE = OFF);")


def capture_evidence(connection, name, scope, directory):
    prefix = "sys.dm_xe_database_" if scope == "DATABASE" else "sys.dm_xe_"
    target = execute_and_consume(connection,
        f"SELECT targets.target_data FROM {prefix}session_targets AS targets "
        f"JOIN {prefix}sessions AS sessions ON sessions.address = targets.event_session_address "
        "WHERE sessions.name = ? AND targets.target_name = 'ring_buffer';", (name,))[0]
    if len(target) != 1 or target[0]["target_data"] is None:
        raise ValueError("The active XEvent ring buffer is unavailable; collection has not been stopped.")
    xml_text = target[0]["target_data"]
    with (directory / "events.xml").open("x", encoding="utf-8") as output:
        output.write(xml_text)
    counters = execute_and_consume(connection,
        f"SELECT dropped_event_count, dropped_buffer_count, largest_event_dropped_size, pending_buffers "
        f"FROM {prefix}sessions WHERE name = ?;", (name,))[0]
    if len(counters) != 1:
        raise ValueError("The XEvent session counters are unavailable.")
    write_json(directory / "event-counters.json", counters[0])
    return xml_text, counters[0]


def run_repetition(connection, settings, columns, directory, repetition):
    directory.mkdir(exist_ok=False)
    run_id = uuid.uuid4()
    name = f"yfcc_search_{run_id.hex}"
    scope = settings["xe_scope"]
    state = {"run_id": str(run_id), "repetition": repetition, "status": "failed",
             "started_utc": datetime.now(timezone.utc).isoformat(), "xe_session": name if repetition else None}
    write_json(directory / "attempt.json", state)
    workload = render_workload(settings["size"], settings["k"], settings["query_count"], run_id)
    with (directory / "workload.sql").open("x", encoding="utf-8") as output:
        output.write(workload)
    result_sets = []
    created = started = False
    evidence = None
    try:
        if repetition:
            ddl = event_session_sql(name, scope, settings["session_id"], run_id, settings["query_count"], columns)
            with (directory / "collection.sql").open("x", encoding="utf-8") as output:
                output.write(ddl)
            execute_and_consume(connection, ddl)
            created = True
            execute_and_consume(connection, f"ALTER EVENT SESSION [{name}] ON {scope} STATE = START;")
            started = True
        execute_and_consume(connection, workload, results=result_sets)
    except (Exception, KeyboardInterrupt) as error:
        state["error"] = f"{type(error).__name__}: {error}"
        if isinstance(error, KeyboardInterrupt):
            state["status"] = "interrupted"
    finally:
        try:
            write_json(directory / "raw-result-sets.json", result_sets)
        except OSError as error:
            state["result_export_error"] = str(error)
        if started:
            try:
                evidence = capture_evidence(connection, name, scope, directory)
            except Exception as error:
                state["evidence_error"] = str(error)
                state["collection_retained"] = True
        if created and (not started or evidence is not None):
            try:
                if started:
                    execute_and_consume(connection, f"ALTER EVENT SESSION [{name}] ON {scope} STATE = STOP;")
                execute_and_consume(connection, f"DROP EVENT SESSION [{name}] ON {scope};")
            except Exception as error:
                state["cleanup_error"] = str(error)
        try:
            if any(key.endswith("error") for key in state):
                raise ValueError("Repetition failed; inspect the retained attempt and evidence before retrying.")
            if len(result_sets) != 1:
                raise ValueError("Expected one per-query result set after completing the batch.")
            rows = result_sets[0]
            if repetition:
                durations = parse_events(evidence[0], run_id, settings["session_id"], settings["query_count"], evidence[1])
                measured = attach_durations(rows, durations, run_id, repetition, settings["k"], settings["requires_page_server_reads"])
                write_json(directory / "queries.json", measured)
                write_query_csv(directory / "queries.csv", measured)
                state.update(status="succeeded", summary=summarize(measured, settings["k"]))
            else:
                validate_rows(rows, settings["query_count"], settings["k"])
                state["status"] = "warmup_discarded"
        except Exception as error:
            state["validation_error"] = str(error)
        write_json(directory / "result.json", state)
    if state["status"] == "interrupted":
        raise KeyboardInterrupt()
    if state["status"] not in ("succeeded", "warmup_discarded"):
        raise RuntimeError(f"Search repetition {repetition} failed. Inspect {directory}; no replay was attempted.")
    return state


def connect(args):
    import pyodbc
    if "ODBC Driver 18 for SQL Server" not in pyodbc.drivers():
        raise ValueError("Microsoft ODBC Driver 18 for SQL Server is required.")
    pyodbc.pooling = False
    attributes = {"DRIVER": "ODBC Driver 18 for SQL Server", "SERVER": args.server, "DATABASE": args.database,
                  "Encrypt": "yes", "TrustServerCertificate": "yes" if args.trust_server_certificate else "no",
                  "APP": "YFCC vector search benchmark", "ConnectRetryCount": "0"}
    if args.trusted_connection:
        attributes["Trusted_Connection"] = "yes"
    else:
        attributes["UID"] = args.username
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            attributes["PWD"] = getpass.getpass("SQL password (not cached): ")
    connection_string = ";".join(key + "={" + value.replace("}", "}}") + "}" for key, value in attributes.items())
    try:
        return pyodbc.connect(connection_string, autocommit=True, timeout=15)
    except pyodbc.Error as error:
        raise RuntimeError(f"ODBC connection failed (SQLSTATE {str(error.args[0])[:5]}). Credentials were not logged.") from None


def preflight(connection, args, directory):
    metadata = execute_and_consume(connection,
        "SELECT @@SPID AS session_id, DB_NAME() AS database_name, CONVERT(varchar(30), SERVERPROPERTY('ProductVersion')) AS engine_version, "
        "@@VERSION AS version_string, CONVERT(int, SERVERPROPERTY('EngineEdition')) AS engine_edition, "
        "CONVERT(nvarchar(128), DATABASEPROPERTYEX(DB_NAME(), 'Edition')) AS service_edition;")[0][0]
    write_json(directory / "target-observed.json", metadata)
    if metadata["database_name"] != args.database or metadata["engine_version"] != args.expected_engine_version:
        raise ValueError("Connected database or engine version differs from the requested target.")
    scope = "DATABASE" if metadata["engine_edition"] in (5, 12) else "SERVER"
    permissions = {row["permission_name"] for row in execute_and_consume(connection,
        f"SELECT permission_name FROM sys.fn_my_permissions(NULL, '{scope}');")[0]}
    required = ({"ALTER ANY DATABASE EVENT SESSION", "VIEW DATABASE STATE"} if scope == "DATABASE"
                else {"ALTER ANY EVENT SESSION", "VIEW SERVER PERFORMANCE STATE"})
    if not required.issubset(permissions):
        raise ValueError(f"XEvent permissions required: {', '.join(sorted(required))}.")
    objects = execute_and_consume(connection,
        "SELECT objects.name, objects.object_type FROM sys.dm_xe_objects AS objects "
        "JOIN sys.dm_xe_packages AS packages ON packages.guid = objects.package_guid "
        "WHERE packages.name = 'sqlserver' AND objects.name IN "
        "('sql_statement_completed', 'sp_statement_completed', 'context_info', 'session_id', 'like_i_sql_unicode_string');")[0]
    available = {(row["name"], row["object_type"]) for row in objects}
    if not {(name, "event") for name in EVENT_NAMES}.issubset(available) or not {
        ("context_info", "action"), ("session_id", "action"), ("like_i_sql_unicode_string", "pred_compare")}.issubset(available):
        raise ValueError("Required public statement-completed events, actions, or predicate are unavailable.")
    columns = execute_and_consume(connection,
        "SELECT columns.object_name, columns.name, columns.type_name, columns.column_type, columns.description "
        "FROM sys.dm_xe_object_columns AS columns JOIN sys.dm_xe_packages AS packages ON packages.guid = columns.object_package_guid "
        "WHERE packages.name = 'sqlserver' AND columns.object_name IN ('sql_statement_completed', 'sp_statement_completed');")[0]
    write_json(directory / "event-metadata.json", columns)
    validate_event_metadata(columns)
    sql = (ROOT / "scripts/validate-search.sql").read_text(encoding="utf-8").replace("__SIZE__", args.size)
    checks = execute_and_consume(connection, sql, (args.query_count, args.k, SIZES[args.size], args.index_name))
    write_json(directory / "population.json", checks)
    service = metadata["service_edition"]
    return {**metadata, "xe_scope": scope,
            "requires_page_server_reads": scope == "DATABASE" and (service is None or service.lower() == "hyperscale")}, columns


def run_search(args):
    if args.size not in SIZES:
        raise ValueError("Choose a supported YFCC Images size: 10M or 100M.")
    if not 1 <= args.query_count <= MAX_QUERY_COUNT:
        raise ValueError(f"Use 1..{MAX_QUERY_COUNT} queries per repetition with the ring-buffer collector.")
    if args.maxdop != 1 or args.k < 1 or args.repetitions < 1:
        raise ValueError("Use MAXDOP=1, positive k and repetitions.")
    manifest_path = args.data_dir / f"yfcc-images-{args.size}" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest["dataset"] != f"yfcc-images-{args.size}" or manifest["document_count"] != SIZES[args.size]
            or manifest["dimensions"] != args.dimension or manifest["metric"] != args.metric
            or manifest["vector_dtype"] != "float32" or args.k > manifest["ground_truth_k"]
            or args.query_count > manifest["query_count"]):
        raise ValueError("Dataset manifest does not match the requested corpus, metric, dimensions, or query range.")
    directory = args.output_dir.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    settings = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "username"}
    settings.update(warmup_passes=1, vector_type="float32", latency_unit="microseconds",
                    latency_source="timing SELECT statement-completed XEvent", fallback_verified=False,
                    cache_state="uncontrolled; validation and paired executions can warm pages",
                    execution_protocol="sequential latency SELECT followed by separate recall INSERT SELECT",
                    credential_mode="windows" if args.trusted_connection else "hidden SQL password prompt")
    write_json(directory / "settings.json", settings)
    write_json(directory / "manifest.json", manifest)
    connection = None
    result = {"status": "failed", "repetitions": []}
    try:
        connection = connect(args)
        target, columns = preflight(connection, args, directory)
        settings.update(target)
        write_json(directory / "target.json", target)
        print("Running one discarded warm-up pass.", flush=True)
        run_repetition(connection, settings, columns, directory / "warmup", 0)
        for repetition in range(1, args.repetitions + 1):
            print(f"Measured repetition {repetition}/{args.repetitions}", flush=True)
            state = run_repetition(connection, settings, columns, directory / f"repetition-{repetition:02d}", repetition)
            result["repetitions"].append(state)
            print(json.dumps(state["summary"]), flush=True)
        result["status"] = "succeeded"
    except (Exception, KeyboardInterrupt) as error:
        result["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        try:
            write_json(directory / "result.json", result)
        finally:
            if connection is not None:
                connection.close()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Measure vector search latency with public XEvents and separate recall executions.")
    parser.add_argument("--size", type=str.upper, choices=SIZES, required=True)
    parser.add_argument("--server", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--expected-engine-version", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--index-name", default="yfcc_vector_index")
    parser.add_argument("--dimension", type=int, choices=[1280], default=1280)
    parser.add_argument("--metric", choices=["euclidean"], default="euclidean")
    parser.add_argument("--query-mode", choices=["ann"], default="ann")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--query-count", type=int, default=MAX_QUERY_COUNT,
                        help=f"Queries per repetition (1..{MAX_QUERY_COUNT}; ring-buffer collector limit).")
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument("--maxdop", type=int, choices=[1], default=1)
    authentication = parser.add_mutually_exclusive_group(required=True)
    authentication.add_argument("--username")
    authentication.add_argument("--trusted-connection", action="store_true")
    parser.add_argument("--trust-server-certificate", action="store_true")
    args = parser.parse_args(argv)
    try:
        run_search(args)
    except KeyboardInterrupt:
        print("Search interrupted. Inspect the retained attempt; nothing was replayed.", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"Search stopped: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())