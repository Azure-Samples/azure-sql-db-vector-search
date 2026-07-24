/*
    Re-rank the RRF results from 007-hybrid-search.sql using the Cohere Rerank
    model deployed on Azure AI Foundry.

    Prereqs:
      - dbo.wikipedia_articles_search_results populated by 007-hybrid-search.sql
      - A Cohere-rerank-v4.0-fast (or -pro) deployment on an Azure AI Foundry
        AIServices resource. Note the deployment name you chose — Azure deployment
        names cannot contain a dot, so a typical deployment name is
        'Cohere-rerank-v4-0-fast'. The 'model' field in the JSON payload below must
        match the deployment name, not the raw model name.

    Token budget: the Cohere rerank GlobalStandard SKU frontend enforces a hard
    ~1000 tokens/min cap regardless of provisioned capacity. For a live demo,
    trim to the top ~5 hybrid results and truncate each document to ~150 chars
    (see LEFT([text], 150) below). Full 50-doc payload will hit RateLimitReached.
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

-- Generate payload for re-ranker, using the top RRF results from hybrid search.
-- Payload format: https://docs.cohere.com/docs/rerank-overview#example-with-structured-data
DECLARE @documents JSON = (
    SELECT JSON_ARRAYAGG('Id: ' || id || CHAR(10) || 'Content: ' || LEFT([text], 150) RETURNING JSON)
    FROM (SELECT TOP 5 * FROM wikipedia_articles_search_results ORDER BY rrf_rank) t
);

DECLARE @payload JSON = JSON_OBJECT(
    'model': 'Cohere-rerank-v4-0-fast',  -- must match your Foundry deployment name (no dots)
    'query': (select q from dbo.wikipedia_search_vectors where id = 1),
    'top_n': 5,
    'documents': @documents
);

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


