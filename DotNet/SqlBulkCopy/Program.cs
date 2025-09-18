using DotNetEnv;
using Microsoft.Data.SqlClient;
using Microsoft.Data.SqlTypes;
using System.Data;

Env.Load();

DataTable table = new();
table.Columns.Add("Id", typeof(int));
table.Columns.Add("Embedding", typeof(SqlVector<float>));
table.Columns.Add("Description", typeof(string));

var embeddingClient = new MockEmbeddingClient();

for (int i = 0; i < 10; i++)
{
    table.Rows.Add(i, new SqlVector<float>(embeddingClient.GetEmbedding($"This is a test {i}")), $"This is a test {i}");
}

Console.WriteLine("Inserting rows with SqlBulkCopy...");
using SqlConnection connection = new(Env.GetString("MSSQL"));
{
    Console.WriteLine("-> Opening connection...");
    connection.Open();

    Console.WriteLine("-> Inserting rows...");
    using SqlBulkCopy bulkCopy = new(connection)
    {
        DestinationTableName = "dbo.SqlBulkCopyEmbedding"
    };
    bulkCopy.WriteToServer(table);
}

Console.WriteLine("Done.");

