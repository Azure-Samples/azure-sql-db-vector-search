# Dapper vector search sample

This folder contains a sample that demonstrates how to store and query vectors in Azure SQL using Dapper.

Files of interest:
- `Dapper.csproj` - .NET console project that uses Dapper and Microsoft.Data.SqlClient.
- `Model.cs` - model classes (Blog, Post, SavedPost).
- `EmbeddingClient.cs` - a small wrapper around Azure OpenAI embeddings (also contains a Mock client).
- `content.json` - sample posts to insert.
- `DatabaseProject/` - a database project that contains the schema (tables with vector column type). Publish this project to your Azure SQL database before running the sample.

How to publish the database project
1. Open `Dapper/DatabaseProject/DapperDatabase.sqlproj` in Visual Studio and publish it to your target SQL Server / Azure SQL.
2. Alternatively, build the database project to produce a `.dacpac` and use `SqlPackage.exe` to publish the `.dacpac` to your server.

Environment
Create a `.env` file in the `Dapper` folder with the following values:

MSSQL=Server=tcp:<your_server>.database.windows.net,1433;Initial Catalog=<your_db>;Persist Security Info=False;User ID=<user>;Password=<password>;MultipleActiveResultSets=False;Encrypt=True;TrustServerCertificate=False;Connection Timeout=30;
OPENAI_KEY=<your_openai_key>
OPENAI_URL=<your_openai_endpoint>
OPENAI_DEPLOYMENT_NAME=<your_embedding_deployment>

Running
1. Publish the database project to the target database.
2. Run this sample from the `Dapper` folder: `dotnet run --project Dapper.csproj`.

Notes
- The sample uses the SQL Server `vector(1536)` column type and passes `SqlVector<float>` parameters when inserting and querying.
- If you do not have access to OpenAI/Azure OpenAI you can swap to `MockEmbeddingClient` in `Program.cs` to run the example locally without network calls.