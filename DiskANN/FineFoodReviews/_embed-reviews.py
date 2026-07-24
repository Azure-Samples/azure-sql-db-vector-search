"""Batch-embed dbo.reviews in chunks of 50 to avoid REST endpoint timeout.
Uses mssql-python (the native Microsoft first-party Python driver).

Configure via environment variables (or edit the defaults below):
  MSSQL_SERVER    e.g. myserver.database.windows.net
  MSSQL_DATABASE  e.g. FineFoodReviews
"""
import os, sys, time
import mssql_python

SERVER = os.getenv("MSSQL_SERVER", "<your-server>.database.windows.net")
DATABASE = os.getenv("MSSQL_DATABASE", "FineFoodReviews")

def connect():
    return mssql_python.connect(
        server=SERVER,
        database=DATABASE,
        authentication="ActiveDirectoryDefault",
    )

conn = connect()
cur = conn.cursor()

# Lock timeout: cap how long DML on this session waits on row locks. This does
# not control external-REST timeout for AI_GENERATE_EMBEDDINGS; that is handled
# by retrying in the loop below.
cur.execute("SET LOCK_TIMEOUT 60000;")

start = time.time()
BATCH = 50
for lo in range(1, 501, BATCH):
    hi = min(lo + BATCH - 1, 500)
    for attempt in range(3):
        try:
            cur.execute(f"""
                UPDATE dbo.reviews
                SET embedding = AI_GENERATE_EMBEDDINGS([combined] USE MODEL AIEmbeddings)
                WHERE embedding IS NULL
                  AND [combined] IS NOT NULL
                  AND Id BETWEEN {lo} AND {hi};
            """)
            conn.commit()
            break
        except mssql_python.Error as e:
            print(f"  retry {attempt+1} on batch {lo}-{hi}: {str(e)[:120]}")
            time.sleep(3)
    cur.execute("SELECT SUM(IIF(embedding IS NOT NULL,1,0)) FROM dbo.reviews")
    total = cur.fetchone()[0]
    print(f"[batch {lo:3d}-{hi:3d}]  embedded so far = {total} / 500   (elapsed {time.time()-start:.1f}s)")

conn.close()
print("[done]")
