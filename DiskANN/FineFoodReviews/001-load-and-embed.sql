/*
    Fine Food Reviews · 001-load-and-embed
    ---------------------------------------------------
    Loads the first 500 rows of Datasets/Reviews.csv into dbo.reviews, then
    generates a VECTOR(1536) embedding for each row via AI_GENERATE_EMBEDDINGS.

    Load options:
      (A) Client-side load (RECOMMENDED for the demo — no blob storage needed).
          Use SqlBulkCopy / bcp / Azure Data Studio's Import wizard to push
          Datasets/Reviews.csv (first 500 rows) into dbo.reviews. Then jump to
          "STEP 2: EMBED" below.

      (B) Server-side load from Azure Blob Storage. Uncomment the BULK INSERT
          block below if you've staged the CSV in the external data source
          declared in 000-setup.sql.
*/
-- Uncomment if using SQL Server 2025:
-- use FineFoodReviews;
-- go

-- ==========================================================================
-- STEP 1 · LOAD  (option B — server-side; keep commented if using option A)
-- ==========================================================================
/*
truncate table dbo.reviews;

bulk insert dbo.reviews (Id, Time, ProductId, UserId, Score, Summary, [Text])
from 'reviews/Reviews.csv'
with (
    data_source     = 'sample_data',
    format          = 'csv',
    firstrow        = 2,
    codepage        = '65001',
    fieldterminator = ',',
    rowterminator   = '0x0a',
    fieldquote      = '"',
    batchsize       = 500,
    lastrow         = 501,           -- keep it small for a live demo
    tablock
);
go
*/

-- ==========================================================================
-- STEP 2 · EMBED
-- ==========================================================================
-- Confirm row count
select count(*) as loaded_rows,
       sum(case when [Text] is not null then 1 else 0 end) as with_text
from dbo.reviews;
go

-- Sanity check the external model
select top (1)
    ai_generate_embeddings(N'hello world' use model AIEmbeddings) as sample_embedding_bytes;
go

-- Bulk-embed all reviews. On 500 rows this is ~30 s over the network.
update dbo.reviews
set embedding = ai_generate_embeddings([combined] use model AIEmbeddings)
where embedding is null
  and [combined] is not null;
go

-- Verify: every row has an embedding
select
    count(*)                              as total_rows,
    sum(iif(embedding is null, 1, 0))     as missing_embeddings,
    min(datalength(embedding))            as min_bytes,
    max(datalength(embedding))            as max_bytes    -- expected: 6152 bytes (1536 × 4 + 8-byte header)
from dbo.reviews;
go

print N'Load + embed complete. Next: 002-diskann-and-fulltext.sql';
