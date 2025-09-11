# Dapper vector search sample

This folder contains a sample that demonstrates how to store and query vectors in Azure SQL using Dapper.

Make sure the create the tables using the scripts in the `db` folder before running the sample.

Create a `.env` file from `.env.example` and fill in the required values, then run the  application

```bash
dotnet run
```

The sample will populate the `Blogs` and `Posts` table with some data. It will then query the database using the vector functions to find similar blog content to a given topic.