USE SemanticShoresDB
GO

/*
    Run sample vector search (over-sample so we have enough candidates to rerank).
    Uses the current syntax: outer TOP (N) WITH APPROXIMATE + ORDER BY distance.
    Older samples used `TOP_N = 50` inside VECTOR_SEARCH — that hint was removed in
    the March 2026 index version.
*/
DECLARE @search_vector VECTOR(1536);
SELECT @search_vector = search_vector
FROM search_phrases
WHERE search_phrase = 'cozy bungalow with original hardwood and charm';

DROP TABLE IF EXISTS #r;
SELECT TOP (50) WITH APPROXIMATE
    t.property_id,
    t.listing_description,
    s.distance AS vector_distance
INTO #r
FROM VECTOR_SEARCH(
    TABLE = properties AS t,
    COLUMN = description_vector,
    SIMILAR_TO = @search_vector,
    METRIC = 'cosine'
) AS s
ORDER BY s.distance;
GO
--SELECT * FROM #r ORDER BY vector_distance;

-- Generate payload for re-ranker, using the result returned by vector search.
-- Payload format: https://docs.cohere.com/docs/rerank-overview#example-with-structured-data
-- Token budget note: Cohere rerank GlobalStandard caps at ~1000 tokens/min. For a
-- live demo trim to top 5 candidates and truncate each description to ~150 chars.
DECLARE @documents JSON = (
    SELECT JSON_ARRAYAGG('Id: ' || property_id || CHAR(10) || 'Content: ' || LEFT(listing_description, 150) RETURNING JSON)
    FROM (SELECT TOP 5 * FROM #r ORDER BY vector_distance) t
);

DECLARE @payload JSON = JSON_OBJECT(
    'model': 'Cohere-rerank-v4-0-fast',  -- must match your Foundry deployment name (no dots)
    'query': 'cozy bungalow with original hardwood and charm',
    'top_n': 5,
    'documents': @documents
);

-- Invoke re-ranker model
DECLARE @response NVARCHAR(MAX);
DECLARE @dummy NVARCHAR(MAX) = CAST(@payload AS NVARCHAR(MAX))
EXEC sp_invoke_external_rest_endpoint
    @url = 'https://<your-endpoint>.services.ai.azure.com/providers/cohere/v2/rerank',
    @credential = [https://<your-endpoint>.services.ai.azure.com/providers/cohere/v2/rerank],
    @payload = @dummy ,
    @response = @response OUTPUT
;

-- Process result and extract Id and Relevance Score
DROP TABLE IF EXISTS #r2;
WITH cte AS 
(
    SELECT 
        CAST(REGEXP_SUBSTR(
            JSON_VALUE(@documents, '$[' || [index] || ']'),
            'Id: (\d*)\n', 1, 1, '', 1
        ) AS INT) AS property_id,
        *
    FROM 
        OPENJSON(@response, '$.result.results')
        WITH (
            [index] INT,
            [relevance_score] DECIMAL(18,10)
        )
)
SELECT
    r.property_id,
    r.listing_description,
    r.vector_distance,
    rr.[index],
    rr.relevance_score
INTO
    #r2
FROM
    #r r
LEFT JOIN
    cte rr ON r.property_id = rr.property_id
GO

-- Return result showing comparsion between original and re-ranked results
SELECT 
    ROW_NUMBER() OVER (ORDER BY vector_distance) as original_position,
    ROW_NUMBER() OVER (ORDER BY relevance_score DESC) as reranked_position,  
    property_id,
    listing_description,
    relevance_score
FROM 
    #r2
ORDER BY 
    relevance_score DESC
GO





