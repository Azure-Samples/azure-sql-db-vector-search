USE SemanticShoresDB
GO

/*
    Run sample vector search
*/
DECLARE @search_vector VECTOR(1536);
SELECT @search_vector = search_vector
FROM search_phrases
WHERE search_phrase = 'cozy bungalow with original hardwood and charm';

DROP TABLE IF EXISTS #r;
SELECT TOP 50  -- Oversample for reranking
    t.property_id,
    t.listing_description,
    s.distance AS vector_distance
INTO
    #r
FROM VECTOR_SEARCH(
    TABLE = properties AS t,
    COLUMN = description_vector,
    SIMILAR_TO = @search_vector,
    METRIC = 'cosine',
    TOP_N = 50
) AS s
ORDER BY s.distance;
GO
--SELECT * FROM #r ORDER BY vector_distance;

-- Generate payload for re-ranker, using the result returned by vector search
-- Payload formatted as per https://docs.cohere.com/docs/rerank-overview#example-with-structured-data
DECLARE @documents JSON = (
    SELECT JSON_ARRAYAGG('Id: ' || property_id || CHAR(10) || 'Content: ' || listing_description RETURNING JSON) FROM #r
)

DECLARE @payload JSON = JSON_OBJECT(
    'model': 'Cohere-rerank-v4.0-fast',
    'query': 'cozy bungalow with original hardwood and charm',
    'top_n': 10,
    'documents': @documents
)

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





