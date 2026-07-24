"""Load first 500 rows of Datasets/Reviews.csv into dbo.reviews on VSLive2026,
then trigger AI_GENERATE_EMBEDDINGS server-side. Uses mssql-python (the native
Microsoft first-party Python driver) with Entra Default auth — no token juggling."""
import csv, sys, time
from pathlib import Path
import mssql_python

SERVER = "antho-test-server.database.windows.net"
DATABASE = "VSLive2026"
CSV = Path("/Users/annahoffman/azure-sql-db-vector-search/Datasets/Reviews.csv")
N_ROWS = 500

def connect():
    return mssql_python.connect(
        server=SERVER,
        database=DATABASE,
        authentication="ActiveDirectoryDefault",
    )

conn = None
try:
    print("[auth] connecting via mssql-python + Entra Default")
    conn = connect()
    print("[auth] connected")
except Exception as e:
    print(f"[auth] failed: {e}")
    sys.exit(1)

cur = conn.cursor()

# Reset + load
print(f"[load] reading first {N_ROWS} rows from {CSV.name}")
rows = []
with CSV.open(newline="", encoding="utf-8") as f:
    reader = csv.reader(f)
    header = next(reader)
    # Expected columns from Amazon Fine Food Reviews:
    # Id, ProductId, UserId, ProfileName, HelpfulnessNumerator, HelpfulnessDenominator, Score, Time, Summary, Text
    print(f"[load] header = {header}")
    idx = {name: i for i, name in enumerate(header)}
    for i, r in enumerate(reader):
        if i >= N_ROWS:
            break
        rows.append((
            int(r[idx["Id"]]),
            int(r[idx["Time"]]) if r[idx["Time"]] else None,
            r[idx["ProductId"]][:50],
            r[idx["UserId"]][:50],
            int(r[idx["Score"]]) if r[idx["Score"]] else None,
            (r[idx["Summary"]] or "")[:500],
            r[idx["Text"]] or "",
        ))
print(f"[load] parsed {len(rows)} rows")

# Insert in batches. combined is a computed column so we don't send it.
print("[insert] deleting old rows")
cur.execute("DELETE FROM dbo.reviews;")
conn.commit()

BATCH = 100
sql = "INSERT INTO dbo.reviews (Id, Time, ProductId, UserId, Score, Summary, [Text]) VALUES (?, ?, ?, ?, ?, ?, ?)"
start = time.time()
for i in range(0, len(rows), BATCH):
    batch = rows[i:i+BATCH]
    cur.executemany(sql, batch)
    conn.commit()
    print(f"[insert] {i+len(batch)}/{len(rows)} (elapsed {time.time()-start:.1f}s)")

print("[insert] complete")
cur.execute("SELECT COUNT(*) FROM dbo.reviews")
print(f"[verify] row count = {cur.fetchone()[0]}")

conn.close()
print("[done]")
