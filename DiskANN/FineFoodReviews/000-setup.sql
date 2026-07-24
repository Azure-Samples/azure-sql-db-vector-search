/*
    Fine Food Reviews · 000-setup
    ------------------------------------------
    Creates the reviews table + external model + external table for CSV load.

    Pre-req: PREVIEW_FEATURES = ON at the database scope.
             Full-text search enabled on the database.
             An Azure OpenAI text-embedding-3-small deployment reachable from the DB
             via database-scoped credential + external URL endpoint.
*/
-- Uncomment if using SQL Server 2025:
-- use FineFoodReviews;
-- go

-- ---------- reviews table ----------
drop table if exists dbo.reviews;
go

create table dbo.reviews (
    Id          int             not null constraint PK_reviews primary key,
    Time        bigint          null,
    ProductId   nvarchar(50)    null,
    UserId      nvarchar(50)    null,
    Score       tinyint         null,           -- 1..5
    Summary     nvarchar(500)   null,           -- short review title
    [Text]      nvarchar(max)   null,           -- long review body
    combined    as (isnull(Summary,'') + N': ' + isnull([Text],'')) persisted,
    embedding   vector(1536)    null            -- populated by 001-load-and-embed.sql
);
go

-- ---------- external model (reuse if already present) ----------
if not exists (select 1 from sys.external_models where name = N'AIEmbeddings')
begin
    print N'AIEmbeddings external model not found. Create it via the pattern in ../Wikipedia/001-setup-objects.sql';
    -- Example (adjust endpoint, deployment name, and credential to your Azure OpenAI resource):
    /*
    create external model AIEmbeddings
    with (
        location    = 'https://<your-aoai>.openai.azure.com/openai/deployments/text-embedding-3-small/embeddings?api-version=2024-08-01-preview',
        api_format  = 'Azure OpenAI',
        model_type  = embeddings,
        model       = 'text-embedding-3-small',
        credential  = [https://<your-aoai>.openai.azure.com]
    );
    */
end;
go

-- ---------- (optional) external data source for CSV load ----------
-- Only needed if loading from Azure Blob Storage. Skip if loading via SqlBulkCopy from a client.
--
-- create database scoped credential [sample_data]
--     with identity = 'Managed Identity';
-- go
-- create external data source [sample_data]
--     with (
--         type     = blob_storage,
--         location = 'https://<myaccount>.blob.core.windows.net/sample-data/',
--         credential = [sample_data]
--     );
-- go

print N'Setup complete. Next: 001-load-and-embed.sql';
