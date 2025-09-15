# EF Core 10 Vector Sample

This sample shows how to use the [native vector functions in EF Core 10](https://learn.microsoft.com/ef/core/what-is-new/ef-core-10.0/whatsnew#vector-search-support) to store and query vector data. You need to have a Azure OpenAI embedding endpoint to run this sample.

More details on vector support in EF Core 10 can be found in the [Vector search in the SQL Server EF Core Provider](https://learn.microsoft.com/en-us/ef/core/providers/sql-server/vector-search) documentation.

Create a `.env` file from `.env.example` and fill in the required values, then run the database migration to create the database tables

```bash
dotnet tool install --global dotnet-ef
dotnet build
dotnet ef database update
```

Run the application

```bash
dotnet run
```

The sample will create a database with a `Blogs` and `Posts` table and seed it with some data. It will then query the database using the vector functions to find similar blog content to a given topic.