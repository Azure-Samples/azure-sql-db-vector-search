-- Step 1: Create a sample table with a VECTOR(5) column
DROP TABLE IF EXISTS dbo.Articles;
CREATE TABLE dbo.Articles 
(
    id INT PRIMARY KEY,
    title NVARCHAR(100),
    content NVARCHAR(MAX),
    embedding VECTOR(5)
);

-- Step 2: Insert sample data
-- 10 named rows for storytelling + 90 generated rows.
-- DiskANN requires at least 100 non-null vectors to build the index.
INSERT INTO dbo.Articles (id, title, content, embedding)
VALUES
(1, 'Intro to AI', 'This article introduces AI concepts.', '[0.1, 0.2, 0.3, 0.4, 0.5]'),
(2, 'Deep Learning', 'Deep learning is a subset of ML.', '[0.2, 0.1, 0.4, 0.3, 0.6]'),
(3, 'Neural Networks', 'Neural networks are powerful models.', '[0.3, 0.3, 0.3, 0.5, 0.1]'),
(4, 'Machine Learning Basics', 'ML basics for beginners.', '[0.4, 0.5, 0.1, 0.7, 0.3]'),
(5, 'Advanced AI', 'Exploring advanced AI techniques.', '[0.5, 0.4, 0.1, 0.1, 0.2]'),
(6, 'AI in Healthcare', 'AI applications in healthcare.', '[0.6, 0.3, 0.4, 0.3, 0.2]'),
(7, 'AI Ethics', 'Ethical considerations in AI.', '[0.1, 0.9, 0.5, 0.4, 0.3]'),
(8, 'AI and Society', 'Impact of AI on society.', '[0.2, 0.3, 0.5, 0.5, 0.4]'),
(9, 'Future of AI', 'Predictions for the future of AI.', '[0.8, 0.4, 0.5, 0.1, 0.2]'),
(10, 'AI Innovations', 'Latest innovations in AI.', '[0.4, 0.7, 0.2, 0.3, 0.1]');
GO

-- Add 90 more rows with pseudo-random 5-dim vectors to satisfy the 100-row minimum for CREATE VECTOR INDEX.
-- Numbers are formatted via CAST(... AS decimal(4,3)) which is locale-invariant (always '.').
INSERT INTO Articles (id, title, content, embedding)
SELECT
    10 + s.value AS id,
    CONCAT(N'Article ', 10 + s.value) AS title,
    CONCAT(N'Filler content ', 10 + s.value) AS content,
    CAST(CONCAT('[',
        CONVERT(varchar(5), CAST(ABS(CHECKSUM(NEWID())) % 1000 / 1000.0 AS decimal(4,3))), ',',
        CONVERT(varchar(5), CAST(ABS(CHECKSUM(NEWID())) % 1000 / 1000.0 AS decimal(4,3))), ',',
        CONVERT(varchar(5), CAST(ABS(CHECKSUM(NEWID())) % 1000 / 1000.0 AS decimal(4,3))), ',',
        CONVERT(varchar(5), CAST(ABS(CHECKSUM(NEWID())) % 1000 / 1000.0 AS decimal(4,3))), ',',
        CONVERT(varchar(5), CAST(ABS(CHECKSUM(NEWID())) % 1000 / 1000.0 AS decimal(4,3))),
    ']') AS VECTOR(5)) AS embedding
FROM GENERATE_SERIES(1, 90) AS s;
GO

SELECT COUNT(*) AS row_count FROM dbo.Articles;
GO

-- Step 3: Create a vector index on the embedding column
CREATE VECTOR INDEX vec_idx ON Articles(embedding)
WITH (METRIC = 'Cosine', TYPE = 'DiskANN')
ON [PRIMARY];
GO

-- Step 4: Perform a vector similarity search
DECLARE @qv VECTOR(5) = (SELECT TOP(1) embedding FROM Articles WHERE id = 1);
SELECT TOP (3) WITH APPROXIMATE
    t.id,
    t.title,
    t.content,
    s.distance
FROM
    VECTOR_SEARCH(
        TABLE = Articles AS t,
        COLUMN = embedding,
        SIMILAR_TO = @qv,
        METRIC = 'Cosine'
    ) AS s
ORDER BY s.distance;
GO

-- Step 5: View index details
SELECT index_id, [type], [type_desc], vector_index_type, distance_metric, build_parameters FROM sys.vector_indexes WHERE [name] = 'vec_idx';
GO

-- Step 6: DML works on a live vector index (current Azure SQL / SQL Server 2025 behavior).
-- INSERT / UPDATE / DELETE are visible in vector search results immediately;
-- the DiskANN graph is maintained asynchronously in the background.
INSERT INTO Articles (id, title, content, embedding)
VALUES
(200, 'Vectors and Embeddings', 'Everything about vectors and embeddings.', '[0.1, 0.2, 0.3, 0.4, 0.6]');
GO

-- Step 7: The new row shows up in vector search immediately
DECLARE @qv VECTOR(5) = (SELECT TOP(1) embedding FROM Articles WHERE id = 1);
SELECT TOP (3) WITH APPROXIMATE
    t.id,
    t.title,
    t.content,
    s.distance
FROM
    VECTOR_SEARCH(
        TABLE = Articles AS t,
        COLUMN = embedding,
        SIMILAR_TO = @qv,
        METRIC = 'Cosine'
    ) AS s
ORDER BY s.distance;
GO

-- Step 8: Observe background maintenance state
SELECT
    OBJECT_NAME(object_id) AS table_name,
    graph_catchup_pending_percent,
    last_background_task_succeeded,
    last_background_task_execution_time,
    last_background_task_processed_inserts,
    last_background_task_processed_deletes
FROM sys.dm_db_vector_indexes
WHERE object_id = OBJECT_ID(N'dbo.Articles');
GO

-- Step 9: Clean up
DROP INDEX vec_idx ON Articles;
DROP TABLE IF EXISTS dbo.Articles;