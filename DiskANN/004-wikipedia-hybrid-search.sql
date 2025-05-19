/*
    Run Hybrid Search using Vector Search and FullText Search and then 
    using Reciprocal Ranking Fusion to calculate the final rank score

	This script requires SQL Server 2025
*/
USE WikipediaTest
go

SET STATISTICS TIME ON
SET STATISTICS IO ON
GO

DECLARE @q NVARCHAR(1000) = 'the foundation series by isaac asimov';
DECLARE @k INT = 10

DECLARE @r INT, @e VECTOR(1536);

SELECT @e = ai_generate_embeddings(@q model Ada2Embeddings);
IF (@r != 0) SELECT @r;

WITH keyword_search AS (
    SELECT TOP(@k)
        id, 
        RANK() OVER (ORDER BY ft_rank DESC) AS [rank],
        title,
        [text]
    FROM
        (
            SELECT TOP(@k)
                id,
                ftt.[RANK] AS ft_rank,
                title,
                [text]
            FROM 
                dbo.wikipedia_articles_embeddings w
            INNER JOIN 
                FREETEXTTABLE(dbo.wikipedia_articles_embeddings, *, @q) AS ftt ON w.id = ftt.[KEY]
            ORDER BY
                ft_rank DESC
        ) AS freetext_documents
    ORDER BY
        rank ASC
),
semantic_search AS
(
    SELECT TOP(@k)
        id, 
        RANK() OVER (ORDER BY cosine_distance) AS [rank]
    FROM
        (
            SELECT TOP(@k)
	            t.id, s.distance as cosine_distance
            FROM
	            VECTOR_SEARCH(
		            TABLE = [dbo].[wikipedia_articles_embeddings] as t, 
		            COLUMN = [content_vector_ada2], 
		            SIMILAR_TO = @e, 
		            METRIC = 'cosine', 
		            TOP_N = @k
	        ) AS s
            ORDER BY cosine_distance
        ) AS similar_documents
),
result AS (
    SELECT TOP(@k)
        COALESCE(ss.id, ks.id) AS id,
        ss.[rank] AS semantic_rank,
        ks.[rank] AS keyword_rank,
        COALESCE(1.0 / (@k + ss.[rank]), 0.0) +
        COALESCE(1.0 / (@k + ks.[rank]), 0.0) AS score -- Reciprocal Rank Fusion (RRF) 
    FROM
        semantic_search ss
    FULL OUTER JOIN
        keyword_search ks ON ss.id = ks.id
    ORDER BY 
        score DESC
)   
SELECT
    w.id,
    cast(score * 1000 as int) as rrf_score,
    rank() OVER(ORDER BY cast(score * 1000 AS INT) DESC) AS rrf_rank,
    semantic_rank,
    keyword_rank,
    w.title,
    w.[text]
FROM
    result AS r
INNER JOIN
    dbo.wikipedia_articles_embeddings AS w ON r.id = w.id
ORDER BY
    rrf_rank