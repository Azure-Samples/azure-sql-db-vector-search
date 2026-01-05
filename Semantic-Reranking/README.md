# Azure SQL and SQL Server Semantic Re-Ranking Sample

This sample demonstrates how to use **vector search with re-ranking** in Azure SQL Database or SQL Server 2025 to improve the relevance of search results. Re-ranking is a two-stage retrieval technique where an initial set of candidates is retrieved using vector similarity search, and then a more sophisticated model re-ranks those results for better relevance.

## Database

This sample uses the **SemanticShores** database, a sample database created and maintained by Joe Sack. The SemanticShores database contains real estate property listings with vector embeddings, making it ideal for demonstrating semantic search and re-ranking scenarios.

**SemanticShores Database Repository:** [https://github.com/MrJoeSack/sqlserver-sample-databases](https://github.com/MrJoeSack/sqlserver-sample-databases/tree/master)

> **Note for Azure SQL Database users:** The SemanticShores database is provided as a backup file (.bak), which cannot be directly restored to Azure SQL Database. To use this sample with Azure SQL DB, you must first restore the backup to SQL Server 2025, then export it as a DACPAC, and finally import the DACPAC into Azure SQL Database.

## Prerequisites

- Azure SQL Database or SQL Server 2025
- SemanticShores database deployed
- **Cohere-rerank-v4.0-fast** model deployed in [Azure AI Foundry](https://ai.azure.com/)
- Database credential configured to access the deployed model (see `setup.sql`)

> **Note:** The Cohere rerank model must be deployed in Azure AI Foundry before running this sample. You can deploy it from the Azure AI Foundry model catalog.

## How It Works

The [rerank.sql](rerank.sql) script demonstrates a complete re-ranking workflow:

### Step 1: Vector Search (Oversampling)

The script first performs a vector similarity search to retrieve the top 50 candidate results. This "oversampling" approach retrieves more results than needed to give the re-ranker a larger pool of candidates to work with:

```sql
SELECT TOP 50  -- Oversample for reranking
    t.property_id,
    t.listing_description,
    s.distance AS vector_distance
FROM VECTOR_SEARCH(
    TABLE = properties AS t,
    COLUMN = description_vector,
    SIMILAR_TO = @search_vector,
    METRIC = 'cosine',
    TOP_N = 50
) AS s
```

### Step 2: Prepare Re-ranker Payload

The results are formatted into a JSON payload compatible with the [Cohere Rerank API](https://docs.cohere.com/docs/rerank-overview):

```sql
DECLARE @documents JSON = (
    SELECT JSON_ARRAYAGG('Id: ' || property_id || CHAR(10) || 'Content: ' || listing_description RETURNING JSON) FROM #r
)

DECLARE @payload JSON = JSON_OBJECT(
    'model': 'Cohere-rerank-v4.0-fast',
    'query': 'cozy bungalow with original hardwood and charm',
    'top_n': 10,
    'documents': @documents
)
```

### Step 3: Invoke Re-ranker Model

The script calls the Cohere re-ranker model using `sp_invoke_external_rest_endpoint`:

```sql
EXEC sp_invoke_external_rest_endpoint
    @url = 'https://<your-endpoint>.services.ai.azure.com/providers/cohere/v2/rerank',
    @credential = [https://<your-endpoint>.services.ai.azure.com/providers/cohere/v2/rerank],
    @payload = @dummy,
    @response = @response OUTPUT
```

The re-ranker returns a JSON response with the re-ranked results:

```json
{
  "id": "ff9ecfdb-1599-4f39-879e-640250c52381",
  "results": [
    {
      "index": 4,
      "relevance_score": 0.812034
    },
    {
      "index": 0,
      "relevance_score": 0.8075214
    },
    {
      "index": 1,
      "relevance_score": 0.80415994
    }
  ],
  "meta": {
    "api_version": {
      "version": "2"
    },
    "billed_units": {
      "search_units": 1
    }
  }
}
```

### Parsing the Re-ranker Response

The Cohere API recommends sending structured data as YAML format (e.g., `Id: 123\nContent: ...`), which means extracting the results back so they can be joined with the original table is tricky. The response only contains the `index` (position in the original documents array) and the `relevance_score`.

Luckily, SQL Server 2025 and Azure SQL now have support for **JSON path expressions** so we can extract exactly the "nth" item from the returned JSON array. Combined with `REGEXP_SUBSTR`, we can extract the ID back from the document text and then join back to the original table:

```sql
WITH cte AS 
(
    SELECT 
        -- Use REGEXP_SUBSTR to extract the ID from the document text
        CAST(REGEXP_SUBSTR(
            JSON_VALUE(@documents, '$[' || [index] || ']'),  -- Get nth document using JSON path
            'Id: (\d*)\n', 1, 1, '', 1  -- Extract the numeric ID
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
FROM
    #r r
LEFT JOIN
    cte rr ON r.property_id = rr.property_id
```

This approach:

1. Uses `OPENJSON` to parse the results array from the response
2. Uses `JSON_VALUE` with a dynamic path expression `$[' || [index] || ']'` to retrieve the original document at the specified index
3. Uses `REGEXP_SUBSTR` to extract the property ID from the YAML-formatted document string
4. Joins back to the original results table to combine vector distances with relevance scores

### Step 4: Compare Results

Finally, the script compares the original vector search ranking with the re-ranked results, showing how the re-ranker can significantly improve result relevance:

```sql
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
```

## Why Re-ranking?

Vector similarity search is fast and efficient for retrieving semantically similar results, but it may not always capture the nuanced relevance that a more sophisticated model can provide. Re-ranking:

- **Improves precision**: The re-ranker model can better understand query intent and document relevance
- **Handles nuance**: Cross-encoder models used in re-ranking consider the full context of both query and document together
- **Balances speed and quality**: By first using fast vector search to narrow candidates, then applying expensive re-ranking only to top results

## Files

| File | Description |
|------|-------------|
| [00-setup.sql](00-setup.sql) | Database credential setup for external REST endpoint |
| [01-credentials.sql](01-credentials.sql) | Credential configuration |
| [02-rerank.sql](02-rerank.sql) | Main re-ranking demonstration script |
| [test.http](test.http) | Sample HTTP request for testing the Cohere rerank API |

## References

- [Cohere Rerank Documentation](https://docs.cohere.com/docs/rerank-overview)
- [Azure SQL Vector Search](https://learn.microsoft.com/azure/azure-sql/database/ai-artificial-intelligence-intelligent-applications)
- [sp_invoke_external_rest_endpoint](https://learn.microsoft.com/sql/relational-databases/system-stored-procedures/sp-invoke-external-rest-endpoint-transact-sql)
