# MSSQL Vector Performance

This sample measures vector index build time, server-side search latency, and
recall using YFCC image vectors. Download, load, build, and search are separate
stages. Build timing excludes loading and table creation, while search requires
an existing compatible vector index.

**Use the demonstrated 10M dataset for the end-to-end workflow.** Downloads need
approximately **51.79 GB**, plus staging space and SQL data, index, and log storage.
Only `10M` and `100M` are supported. The `1M` option was removed because its
published ground truth is incompatible with its corpus. Existing downloads and
results are left untouched. Do not remap or discard invalid neighbor IDs.

## Disclaimer
These scripts and accompanying results are provided for informational and illustrative purposes only. They are intended to demonstrate how vector index build and vector search performance can be measured for Azure SQL Database under the specific configurations and workloads described in this repository.
Performance results were obtained using the specified dataset, workload, database configuration, compute configuration, and test environment. Actual performance may vary depending on factors including data characteristics and size, vector dimensions, index configuration, query patterns, concurrency, service tier, compute resources, system load, and other environmental conditions.
The results presented here should not be interpreted as a performance guarantee, service-level commitment, or prediction of performance for a particular production workload. They are also not intended as comparative benchmark results against other products or services.
Customers should evaluate performance using their own data, workloads, configurations, and production requirements before making deployment or capacity-planning decisions.
MICROSOFT MAKES NO WARRANTIES, EXPRESS OR IMPLIED, WITH RESPECT TO THE INFORMATION, SCRIPTS, OR RESULTS PROVIDED HERE.

## Prerequisites

The commands below use Windows, PowerShell, and Windows authentication on a local
SQL Server. Build `18.0.251.0` was tested. Azure SQL authentication and
database-scoped XEvents require separate live validation; the local run does not
establish Azure SQL compatibility or performance.

- Install Python 3.11 or newer and the packages in [requirements.txt](requirements.txt).
- Install [Microsoft ODBC Driver 18](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server).
- Install [BCP](https://learn.microsoft.com/en-us/sql/tools/bcp/bcp-download-install)
  reporting version 18.6.1.1 or newer and [sqlcmd](https://learn.microsoft.com/en-us/sql/tools/sqlcmd/sqlcmd-download-install).
  Native float32 vector transfer requires `-n -z0`.
- Prepare a dedicated user database supporting `VECTOR(1280)`, DiskANN,
  `TOP ... WITH APPROXIMATE`, and `FORCE_ANN_ONLY`. Enable any required preview
  features yourself; the scripts do not change server or database settings.
- Grant table-creation, bulk-import, SELECT, and ALTER permissions. Server-scoped
  search collection also requires `ALTER ANY EVENT SESSION` and
  `VIEW SERVER PERFORMANCE STATE`.

Use an empty destination for loading and avoid concurrent writes during the
benchmark. Inspect the engine and client versions before starting. If PATH
selects older tools, pass explicit `--bcp` and `--sqlcmd` paths to the load stage.

## Run The Four Stages

From the repository root, prepare the Python environment:

```powershell
Set-Location azure-sql-vector-performance
python -m pip install -r requirements.txt
```

The example assumes an existing database named `MSSQLVectorBenchmark`. Replace
the server and database values for your target. The certificate-trust switch is
only for a local test server with an untrusted certificate; omit it when the
certificate is trusted. Finish each stage before starting the next.

```powershell
python benchmark.py download --size 10M

python benchmark.py load --size 10M --server tcp:localhost,1433 --database MSSQLVectorBenchmark --trusted-connection --trust-server-certificate

python benchmark.py build --size 10M --server tcp:localhost,1433 --database MSSQLVectorBenchmark --trusted-connection --trust-server-certificate --maxdop 1 --output-dir data/build-runs/10M-first

python benchmark.py search --size 10M --server tcp:localhost,1433 --database MSSQLVectorBenchmark --trusted-connection --trust-server-certificate --expected-engine-version 18.0.251.0 --query-count 10 --repetitions 1 --output-dir data/search-runs/10M-first
```

Search starts with ten queries and one measured repetition. Its version pin is
currently required; replace the example with your observed engine version.
Build accepts the pin optionally. A matching version alone does not guarantee
that every required feature is available.

After the small run succeeds, use `--query-count 1000 --repetitions 10` with a new
output directory. Search accepts 1-1,000 queries per repetition; larger counts
are rejected before connecting. This is the sample's validated ring-buffer
collection limit, not a SQL search limit. Use a stage's `--help` for more options.

SQL authentication uses `--username` instead of `--trusted-connection` and hidden
password prompts. Passwords are not cached. The default 10M load requires about
205 prompts, so the tested local workflow uses Windows authentication. Windows
trusted authentication is not supported by Azure SQL Database, and this sample
does not implement Entra authentication.

## Dataset And Loading

[Big ANN Benchmarks](https://github.com/harsha-simhadri/big-ann-benchmarks/blob/main/benchmark/datasets.py)
defines the YFCC Images dataset: 1,280-dimensional float32 vectors, 100,000 query
vectors, Euclidean distance, and size-specific ground truth. The reported GT
depth is 100. Document/query IDs are zero-based source positions; GT ranks are
one-based. Check dataset licensing before redistributing downloaded files.

| Size | Document count | Download space |
| --- | ---: | ---: |
| 10M | 10,000,000 | 51.79 GB |
| 100M | 98,735,605 | 506.12 GB |

These decimal sizes include queries and ground truth. Only 10M has completed
the demonstrated full workflow; 100M has not been validated end to end here.

Downloads go to `data/yfcc-images-SIZE` beside the scripts. Use the same
`--data-dir` parent across stages when choosing another location. Each dataset
contains `base.bin`, `queries.bin`, `groundtruth.bin`, and a manifest with source
URLs, shapes, byte counts, and local SHA-256 hashes. These are integrity records,
not publisher checksums or proof of exact nearest neighbors.

Downloads are sequential. Completed files are skipped without rehashing, and
interrupted `.part` files restart from the beginning. There is no automatic retry
or byte-level resume. Before any SQL/tool calls or staging output, loading checks
source shapes and scans all GT IDs, distances, and duplicate neighbors. GT values
are checked again during conversion; non-finite vectors are rejected per chunk.
These checks preserve source files and do not establish exact nearest neighbors.

`--chunk-rows` defaults to 100,000 source rows per temporary file. Independently,
`--batch-size` defaults to 10,000 imported rows per BCP transaction. A default
vector chunk needs about 490 MiB; a depth-100 GT chunk needs about 153 MiB. Error
files and SQL storage require additional space. Each chunk is imported, checked
for rejected or missing rows, and removed only after successful verification.

A complete 10M load has 10,000,000 documents, 100,000 queries, and 10,000,000 GT
rows in `dbo.yfcc_10M_documents`, `dbo.yfcc_10M_queries`, and
`dbo.yfcc_10M_groundtruth`. Table creation and verification SQL are in
[scripts/setup/create-table.sql](scripts/setup/create-table.sql) and
[scripts/setup/load-data.sql](scripts/setup/load-data.sql).

## Measurement Method

### Index Build

Each invocation measures one fresh CREATE with no build warm-up. The runner
records the actual population, engine version, exact SQL, and requested settings.
Build MAXDOP is explicit: `1` suppresses parallel plans, while `0` permits
server-selected parallelism and does not mean one worker. Omitted options are
recorded as server defaults without guessing their effective values.

The metric is **server-side CREATE VECTOR INDEX elapsed time**.
[scripts/build-index.sql](scripts/build-index.sql) measures the interval around
CREATE using `SYSUTCDATETIME()` and `DATEDIFF_BIG`. It includes server execution
and waits but excludes connection setup, validation, approved DROP operations,
postchecks, and export. It is neither CPU time nor a Python client timer. The
clock is not monotonic, so clock adjustments can affect the result.

### Search Latency And Recall

Defaults are k=10, 1,000 queries, one discarded warm-up, ten measured repetitions,
and MAXDOP=1. Each repetition sends one sequential server-side loop, visible in
[scripts/vector-search.sql](scripts/vector-search.sql), on a dedicated connection.

Each query executes twice: a timing SELECT consumes IDs on the server, then a
separate execution captures IDs for recall. The pair fails if row counts differ.
`CONTEXT_INFO` identifies the run, query, and execution kind. Per-query latency
comes from the timing SELECT's public statement-completed XEvent, not a wall-clock
delta. Events are filtered by session and their own statement text. Missing,
duplicate, dropped, or truncated evidence invalidates the repetition; evidence
is saved before collection stops.

Recall@k is distinct overlap with validated GT top-k divided by k. Three correct
neighbors at k=10 means 30%, even if only three are returned. Short and empty
successful answers remain in summaries; failed queries never become empty answers.
Mean recall is the arithmetic mean across queries. p50 and p95 use individual
durations with linear interpolation at `(n - 1) * p` (type 7). Milliseconds equal
microseconds divided by 1000.0.

Equal row counts do not prove identical neighbors across the two executions.
The second can benefit from the first, so this is not a single-search throughput
test. Validation and warm-up can warm pages; neither cold-cache nor warm-plan-cache
execution is claimed. Hot data reads require zero physical reads and, on Hyperscale,
zero page-server reads. Missing required counters mean unknown. Read-bearing results
are retained, and absence of fallback is not independently verified.

## Results And Recovery

Build saves `request.json`, a CREATE completion checkpoint, and final JSON/CSV
results. Search saves settings, SQL, raw rows, XEvent evidence, and summaries.
Each validated measured pass writes `queries.csv` with run/repetition/query IDs,
returned and matched counts, GT count, latency in microseconds and milliseconds,
recall, read counters, and hot status. Recall is a 0-1 fraction; unavailable
counters are blank, not zero. Warm-up is excluded from measured CSVs. Generated
CSVs and datasets remain ignored by Git.

Existing outputs are never overwritten. Loading does not drop or truncate tables.
An existing empty staging directory is allowed, but setup still refuses existing
destination tables. Nonempty staging requires inspection before another attempt.
Build replacement requires `--replace-existing` and confirmation of the exact
index name; search never replaces indexes. Failed chunks and available evidence
remain for inspection. Earlier BCP transactions may have committed, so never
replay a failed load blindly. No automatic rollback or resume is performed.

CREATE completion, successful postchecks, and successful export are distinct.
After an export failure, inspect all retained records rather than trusting one
CSV status. Recover build reporting without a database connection or another CREATE:

```powershell
python benchmark.py build --recover-result data/build-runs/10M-first
```

Recovery writes new files. A partial export or missing completion checkpoint
must not be treated as a successful measurement.

## Validation And Tests

A local SQL Server `18.0.251.0` run completed 10M load, build, and search on
2026-09-24 using publisher GT, build MAXDOP=16, and search MAXDOP=1. It checked
10,000 query records and uniquely attributed timing events. This is execution
evidence, not an independent exact-GT audit, full-corpus readback, or an Azure SQL
performance guarantee. No portable performance results are published here. The
run used a separate parallel-download helper, not the sample's sequential downloader.

A separate 100,000-query collection experiment on the same build completed all
result rows, but the ring buffer retained only 3,795 events and serialized 1,909
into truncated XML. The runner rejected the evidence and published no success CSV.
The 1,000-query cap prevents such unsupported repetitions from starting.

Run offline tests from this sample directory:

```powershell
python -m unittest discover -s tests -v
```

Tests use local HTTP fixtures and mocked SQL calls. The live loader test is
opt-in through `MSSQL_VECTOR_LIVE_TEST=1` and requires a dedicated empty database;
review [tests/test_live_load.py](tests/test_live_load.py) before enabling it.
Offline tests do not replace live validation on the intended server and clients.