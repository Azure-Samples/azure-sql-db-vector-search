# Quickstart: Vector search with TypeScript in Azure SQL Database

This sample demonstrates how to perform **native vector search** in Azure SQL Database using TypeScript and Node.js.

It uses:

- **[tedious](https://www.npmjs.com/package/tedious)** — Microsoft's Node.js driver for SQL Server, with Azure AD authentication
- **[@azure/openai](https://www.npmjs.com/package/@azure/openai)** + **[openai](https://www.npmjs.com/package/openai)** — Azure OpenAI SDK for generating embeddings
- **[@azure/identity](https://www.npmjs.com/package/@azure/identity)** — `DefaultAzureCredential` for passwordless authentication to both Azure SQL and Azure OpenAI

## What the sample does

1. Connects to Azure SQL Database using `DefaultAzureCredential` (no passwords or API keys)
2. Creates a table with a `VECTOR(1536)` column
3. Generates text embeddings using Azure OpenAI `text-embedding-3-small`
4. Inserts sample hotel data with vector embeddings
5. Performs a vector similarity search using `VECTOR_DISTANCE()`
6. Displays the top matching results with similarity scores

## Prerequisites

- **Azure subscription** — [Create one free](https://azure.microsoft.com/free/)
- **Azure SQL Database** with native vector support — [Quickstart: Create a single database](https://learn.microsoft.com/azure/azure-sql/database/single-database-create-quickstart)
- **Azure OpenAI resource** with a `text-embedding-3-small` deployment — [Create and deploy an Azure OpenAI Service resource](https://learn.microsoft.com/azure/ai-services/openai/how-to/create-resource)
- **Node.js 20+** — [Download Node.js](https://nodejs.org/)
- **Azure CLI** — [Install the Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli), signed in with `az login`

> [!IMPORTANT]
> Your Azure identity must have access to both the Azure SQL Database and the Azure OpenAI resource. Assign yourself the **SQL DB Contributor** role on the SQL server and the **Cognitive Services OpenAI User** role on the OpenAI resource, or equivalent permissions.

## Get started

### 1. Clone the repository

```bash
git clone https://github.com/Azure-Samples/azure-sql-db-vector-search.git
cd azure-sql-db-vector-search/TypeScript
```

### 2. Install dependencies

```bash
npm install
```

### 3. Configure environment variables

Copy the sample environment file and fill in your values:

```bash
cp sample.env .env
```

Edit `.env` with your Azure resource details:

```env
AZURE_SQL_SERVER=<your-server>.database.windows.net
AZURE_SQL_DATABASE=<your-database>
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small
```

> [!NOTE]
> No API keys are needed. The sample uses `DefaultAzureCredential`, which automatically uses your Azure CLI login, managed identity, or other credential sources.

### 4. Run the sample

```bash
npm start
```

This runs the TypeScript code directly using `tsx` with Node.js 20+ native env-file loading.

## Expected output

```
=== Azure SQL Vector Search — TypeScript Quickstart ===

Server:     <your-server>.database.windows.net
Database:   <your-database>
OpenAI:     https://<your-resource>.openai.azure.com
Deployment: text-embedding-3-small

Connecting to Azure SQL Database...
Connected.

Creating hotels table (if not exists)...
Table ready.

Generating embeddings with Azure OpenAI...
Generated 5 embeddings (dimension: 1536).

Inserting hotel data with embeddings...
  Inserted: Oceanview Resort & Spa
  Inserted: Mountain Lodge Retreat
  Inserted: Downtown City Hotel
  Inserted: Desert Oasis Inn
  Inserted: Lakeside Cabin Village

Searching for: "luxury beachfront hotel with ocean views and spa"

--- Search Results (Top 3 by Cosine Distance) ---

  Hotel:       Oceanview Resort & Spa
  Description: A luxurious beachfront resort offering stunning ocean views, a full-service spa, infin...
  Distance:    0.1234
  Similarity:  0.8766

  Hotel:       Lakeside Cabin Village
  Description: Rustic yet comfortable lakeside cabins surrounded by forest. Enjoy kayaking, fishing, ...
  Distance:    0.3456
  Similarity:  0.6544

  Hotel:       Desert Oasis Inn
  Description: A unique desert retreat with adobe-style architecture, stargazing terrace, and cactus ...
  Distance:    0.3789
  Similarity:  0.6211

Done. Connection closed.
```

> [!NOTE]
> Actual distance and similarity values will vary based on the embedding model's output.

## Understanding the code

### Connection with DefaultAzureCredential

The sample uses `tedious` with Azure AD token-based authentication. A token is acquired from `DefaultAzureCredential` for the `https://database.windows.net/.default` scope:

```typescript
const credential = new DefaultAzureCredential();
const token = await credential.getToken("https://database.windows.net/.default");
```

### Table with VECTOR column

Azure SQL Database supports the native `VECTOR` type. The table is created with a `VECTOR(1536)` column to store embeddings:

```sql
CREATE TABLE dbo.hotels_typescript (
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(200) NOT NULL,
    description NVARCHAR(MAX) NOT NULL,
    embedding VECTOR(1536) NULL
);
```

### Generating embeddings

Embeddings are generated using Azure OpenAI's `text-embedding-3-small` model through the `openai` SDK with `@azure/identity` for authentication:

```typescript
import { getBearerTokenProvider } from "@azure/identity";
import { AzureOpenAI } from "openai";

const azureADTokenProvider = getBearerTokenProvider(
    credential,
    "https://cognitiveservices.azure.com/.default"
);
const openaiClient = new AzureOpenAI({
    endpoint: config.azureOpenAiEndpoint,
    azureADTokenProvider,
    apiVersion: "2024-10-21",
});

const response = await openaiClient.embeddings.create({
    model: deployment,
    input: texts,
});
```

### Vector similarity search

The `VECTOR_DISTANCE()` T-SQL function computes cosine distance between the query vector and stored embeddings:

```sql
SELECT TOP 3
    name, description,
    VECTOR_DISTANCE('cosine', embedding, CAST(@queryVector AS VECTOR(1536))) AS distance
FROM dbo.hotels_typescript
ORDER BY distance;
```

A lower distance means higher similarity.

## Clean up resources

To remove the sample table from your database:

```sql
DROP TABLE IF EXISTS dbo.hotels_typescript;
```

To avoid ongoing charges, delete the Azure resources you created if they were only for this quickstart:

- [Delete the Azure SQL Database](https://learn.microsoft.com/azure/azure-sql/database/single-database-manage#delete-a-single-database)
- [Delete the Azure OpenAI resource](https://learn.microsoft.com/azure/ai-services/openai/how-to/create-resource#delete-a-resource)

## Related content

- [Vectors in Azure SQL and SQL Server](https://learn.microsoft.com/sql/sql-server/ai/vectors)
- [VECTOR_DISTANCE (Transact-SQL)](https://learn.microsoft.com/sql/t-sql/functions/vector-distance-transact-sql)
- [Azure OpenAI text embeddings](https://learn.microsoft.com/azure/ai-services/openai/concepts/models#embeddings)
- [DefaultAzureCredential overview](https://learn.microsoft.com/javascript/api/overview/azure/identity-readme#defaultazurecredential)
