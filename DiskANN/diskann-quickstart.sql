CREATE DATABASE DiskANNQuickstart;
GO

USE DiskANNQuickstart;
GO

-- Step 0: Enable Preview Feature
DBCC TRACEON(466, 474, 13981, -1) 
GO

-- Step 1: Create a sample table with a VECTOR(5) column
CREATE TABLE dbo.Articles 
(
    id INT PRIMARY KEY,
    title NVARCHAR(100),
    content NVARCHAR(MAX),
    embedding VECTOR(5)
);

-- Step 2: Insert sample data
INSERT INTO Articles (id, title, content, embedding)
VALUES
(1, 'Intro to AI', 'This article introduces AI concepts.', '[0.1, 0.2, 0.3, 0.4, 0.5]'),
(2, 'Deep Learning', 'Deep learning is a subset of ML.', '[0.2, 0.1, 0.4, 0.3, 0.6]'),
(3, 'Neural Networks', 'Neural networks are powerful models.', '[0.3, 0.3, 0.2, 0.5, 0.1]'),
(4, 'Machine Learning Basics', 'ML basics for beginners.', '[0.4, 0.5, 0.1, 0.2, 0.3]'),
(5, 'Advanced AI', 'Exploring advanced AI techniques.', '[0.5, 0.4, 0.6, 0.1, 0.2]');

-- Step 3: Create a vector index on the embedding column
CREATE VECTOR INDEX vec_idx ON Articles(embedding)
WITH (metric = 'cosine', type = 'diskann');

-- Step 4: Perform a vector similarity search
DECLARE @qv VECTOR(5) = '[0.3, 0.3, 0.3, 0.3, 0.3]';
SELECT
    t.id,
    t.title,
    t.content,
    s.distance
FROM
    VECTOR_SEARCH(
        table = Articles AS t,
        column = embedding,
        similar_to = @qv,
        metric = 'cosine',
        top_n = 3
    ) AS s
ORDER BY s.distance, t.title;
