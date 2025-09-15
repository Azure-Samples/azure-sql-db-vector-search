# EF Core 9 Vector Sample

This sample shows how to use the vector functions in EF Core to store and query vector data. It is an end-to-end sample using the extension [`EFCore.SqlServer.VectorSearch`](https://github.com/efcore/EFCore.SqlServer.VectorSearch) package.

You need to have a Azure OpenAI embedding endpoint to run this sample.

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