/*
    Test the half-precision (fp16) VECTOR support.
    Converts the existing fp32 embeddings to fp16, builds a DiskANN index on
    both, and compares storage size + recall of ANN(fp32) vs ANN(fp16) vs KNN(fp32).

    Prereqs (from earlier scripts):
      - dbo.wikipedia_articles_embeddings loaded with 25000 rows
      - content_vector (VECTOR(1536)) populated
      - EXTERNAL MODEL Ada2Embeddings (text-embedding-ada-002) -- the corpus was
        embedded with ada-002; querying with a different 1536-dim model gives noise
*/
-- Uncomment if using SQL Server 2025
-- USE WikipediaTest
-- GO

-- ---------------------------------------------------------------------------
-- Step 1. Add the fp16 column (skip if it already exists)
-- ---------------------------------------------------------------------------
IF COL_LENGTH('dbo.wikipedia_articles_embeddings', 'content_vector_fp16') IS NULL
BEGIN
    ALTER TABLE [dbo].[wikipedia_articles_embeddings]
    ADD content_vector_fp16 VECTOR(1536, float16);
END
GO

-- View the metadata: fp32 vs fp16 columns side by side
SELECT
    [name] AS column_name,
    system_type_id,
    user_type_id,
    vector_dimensions,
    vector_base_type,
    vector_base_type_desc
FROM sys.columns
WHERE object_id = OBJECT_ID('[dbo].[wikipedia_articles_embeddings]')
  AND vector_dimensions IS NOT NULL;
GO

-- ---------------------------------------------------------------------------
-- Step 2. Drop existing vector indexes so we can rebuild against both columns
-- ---------------------------------------------------------------------------
SELECT i.name AS index_name
FROM sys.vector_indexes v
JOIN sys.indexes i ON v.object_id = i.object_id AND v.index_id = i.index_id
WHERE v.object_id = OBJECT_ID('dbo.wikipedia_articles_embeddings');
GO

DROP INDEX IF EXISTS vec_idx   ON [dbo].[wikipedia_articles_embeddings];
DROP INDEX IF EXISTS vec_idx2  ON [dbo].[wikipedia_articles_embeddings];
DROP INDEX IF EXISTS vec_idx32 ON [dbo].[wikipedia_articles_embeddings];
DROP INDEX IF EXISTS vec_idx16 ON [dbo].[wikipedia_articles_embeddings];
GO

-- ---------------------------------------------------------------------------
-- Step 3. Materialize fp16 from fp32
-- Note: direct CAST from VECTOR to VECTOR is not supported yet; go via JSON.
-- ---------------------------------------------------------------------------
UPDATE [dbo].[wikipedia_articles_embeddings]
SET content_vector_fp16 = CAST(CAST(content_vector AS JSON) AS VECTOR(1536, float16))
WHERE content_vector_fp16 IS NULL;
GO

-- Compare storage: fp16 is half the size of fp32 on disk
SELECT TOP 5
    id, title,
    DATALENGTH(content_vector)      AS fp32_bytes,
    DATALENGTH(content_vector_fp16) AS fp16_bytes
FROM [dbo].[wikipedia_articles_embeddings]
WHERE title LIKE 'Philosoph%';
GO

-- ---------------------------------------------------------------------------
-- Step 4. Prepare query vectors (fp32 + fp16 for the same text)
-- Uses Ada2Embeddings because the corpus was embedded with ada-002.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS #t;
CREATE TABLE #t (id INT, q NVARCHAR(MAX), v32 VECTOR(1536, float32), v16 VECTOR(1536, float16));

INSERT INTO #t (id, q, v32)
SELECT id, q, AI_GENERATE_EMBEDDINGS(q USE MODEL Ada2Embeddings)
FROM (VALUES
    (1, N'four legged furry animal'),
    (2, N'pink floyd music style')
) s(id, q);

UPDATE #t SET v16 = CAST(CAST(v32 AS JSON) AS VECTOR(1536, float16));

SELECT id, q, DATALENGTH(v32) AS v32_bytes, DATALENGTH(v16) AS v16_bytes FROM #t;
GO

-- ---------------------------------------------------------------------------
-- Step 5. Build DiskANN indexes on both columns
-- ---------------------------------------------------------------------------
CREATE VECTOR INDEX vec_idx32 ON [dbo].[wikipedia_articles_embeddings](content_vector)
    WITH (METRIC = 'cosine', TYPE = 'diskann');
GO

CREATE VECTOR INDEX vec_idx16 ON [dbo].[wikipedia_articles_embeddings](content_vector_fp16)
    WITH (METRIC = 'cosine', TYPE = 'diskann');
GO

SELECT i.name, JSON_VALUE(v.build_parameters, '$.Version') AS version
FROM sys.vector_indexes v
JOIN sys.indexes i ON v.object_id = i.object_id AND v.index_id = i.index_id
WHERE v.object_id = OBJECT_ID('dbo.wikipedia_articles_embeddings');
GO

SET STATISTICS TIME ON;
SET STATISTICS IO   ON;
GO

-- ---------------------------------------------------------------------------
-- Step 6. KNN (exact) on the fp16 column
-- ---------------------------------------------------------------------------
DECLARE @qv VECTOR(1536, float16) = (SELECT TOP(1) v16 FROM #t WHERE id = 2);
SELECT TOP (50) id, VECTOR_DISTANCE('cosine', @qv, content_vector_fp16) AS distance, title
FROM [dbo].[wikipedia_articles_embeddings]
ORDER BY distance;
GO

-- ---------------------------------------------------------------------------
-- Step 7. ANN (approximate) on the fp16 column
-- New syntax: TOP (N) WITH APPROXIMATE ... ORDER BY distance
-- ---------------------------------------------------------------------------
DECLARE @qv VECTOR(1536, float16) = (SELECT TOP(1) v16 FROM #t WHERE id = 2);
SELECT TOP (50) WITH APPROXIMATE
    t.id, s.distance, t.title
FROM VECTOR_SEARCH(
    TABLE = [dbo].[wikipedia_articles_embeddings] AS t,
    COLUMN = content_vector_fp16,
    SIMILAR_TO = @qv,
    METRIC = 'cosine'
) AS s
ORDER BY s.distance;
GO

-- ---------------------------------------------------------------------------
-- Step 8. Recall comparison: KNN(fp32) baseline vs ANN(fp32) vs ANN(fp16)
-- Both fp16 ANN and fp32 ANN measured against the exact fp32 KNN result.
-- ---------------------------------------------------------------------------
DECLARE @n INT = 100;
DECLARE @qv32 VECTOR(1536, float32), @qv16 VECTOR(1536, float16);
SELECT TOP(1) @qv32 = v32, @qv16 = v16 FROM #t WHERE id = 1;

WITH cteANN32 AS (
    SELECT TOP (@n) WITH APPROXIMATE t.id, s.distance, t.title
    FROM VECTOR_SEARCH(
        TABLE = [dbo].[wikipedia_articles_embeddings] AS t,
        COLUMN = content_vector,
        SIMILAR_TO = @qv32,
        METRIC = 'cosine'
    ) AS s
    ORDER BY s.distance
),
cteANN16 AS (
    SELECT TOP (@n) WITH APPROXIMATE t.id, s.distance, t.title
    FROM VECTOR_SEARCH(
        TABLE = [dbo].[wikipedia_articles_embeddings] AS t,
        COLUMN = content_vector_fp16,
        SIMILAR_TO = @qv16,
        METRIC = 'cosine'
    ) AS s
    ORDER BY s.distance
),
cteKNN32 AS (
    SELECT TOP (@n) id, VECTOR_DISTANCE('cosine', @qv32, content_vector) AS distance, title
    FROM [dbo].[wikipedia_articles_embeddings]
    ORDER BY distance, id
)
SELECT
    k32.id AS id_knn,
    a32.id AS id_ann_fp32,
    a16.id AS id_ann_fp16,
    k32.distance AS distance_knn,
    a32.distance AS distance_ann_fp32,
    a16.distance AS distance_ann_fp16,
    CAST(CAST(COUNT(a32.id) OVER (ORDER BY k32.distance) AS FLOAT)
       / CAST(COUNT(k32.id) OVER (ORDER BY k32.distance) AS FLOAT) AS DECIMAL(6,3)) AS running_recall_fp32,
    CAST(CAST(COUNT(a16.id) OVER (ORDER BY k32.distance) AS FLOAT)
       / CAST(COUNT(k32.id) OVER (ORDER BY k32.distance) AS FLOAT) AS DECIMAL(6,3)) AS running_recall_fp16
FROM cteKNN32 k32
LEFT OUTER JOIN cteANN32 a32 ON k32.id = a32.id
LEFT OUTER JOIN cteANN16 a16 ON k32.id = a16.id
ORDER BY k32.distance;
GO
