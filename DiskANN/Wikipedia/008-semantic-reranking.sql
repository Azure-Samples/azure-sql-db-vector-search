/*
    Run Hybrid Search using Vector Search and FullText Search and then 
    using Reciprocal Ranking Fusion to calculate the final rank score

    Results are saved into dbo.wikipedia_articles_search_results so that they can be reused
    in the next script
*/
-- Uncomment if using SQL Server 2025
--use WikipediaTest
--go

if not exists(select * from sys.database_scoped_credentials where [name] = 'https://<endpoint>.services.ai.azure.com/providers/cohere/v2/rerank')
begin
    create database scoped credential [https://<endpoint>.services.ai.azure.com/providers/cohere/v2/rerank]
    --with identity = 'Managed Identity', secret = '{"resourceid":"https://cognitiveservices.azure.com"}';
	--or
	with identity = 'HTTPEndpointHeaders', secret = '{"api-key":"<api-key>"}';
end
go

-- Generate payload for re-ranker, using the result returned by vector search
-- Payload formatted as per https://docs.cohere.com/docs/rerank-overview#example-with-structured-data
DECLARE @documents JSON = (
    SELECT JSON_ARRAYAGG('Id: ' || id || CHAR(10) || 'Content: ' || [text] RETURNING JSON) FROM wikipedia_articles_search_results
)

DECLARE @payload JSON = JSON_OBJECT(
    'model': 'Cohere-rerank-v4.0-fast',
    'query': (select q from dbo.wikipedia_search_vectors where id = 1),
    'top_n': 10,
    'documents': @documents
)

-- Invoke re-ranker model
DECLARE @response NVARCHAR(MAX);
DECLARE @dummy NVARCHAR(MAX) = CAST(@payload AS NVARCHAR(MAX))
EXEC sp_invoke_external_rest_endpoint
    @url = 'https://<endpoint>.services.ai.azure.com/providers/cohere/v2/rerank',
    @credential = [https://<endpoint>.services.ai.azure.com/providers/cohere/v2/rerank],
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
        ) AS INT) AS id,
        *
    FROM 
        OPENJSON(@response, '$.result.results')
        WITH (
            [index] INT,
            [relevance_score] DECIMAL(18,10)
        )
)
SELECT
    r.id,
    r.title,
    r.rrf_score,
    rr.[index],
    rr.relevance_score
INTO
    #r2
FROM
    wikipedia_articles_search_results r
LEFT JOIN
    cte rr ON r.id = rr.id
GO

-- Return result showing comparsion between original and re-ranked results
SELECT 
    ROW_NUMBER() OVER (ORDER BY rrf_score DESC) as original_position,
    ROW_NUMBER() OVER (ORDER BY relevance_score DESC) as reranked_position,  
    id,
    title,
    rrf_score,
    relevance_score
FROM 
    #r2
ORDER BY 
    relevance_score DESC
GO


