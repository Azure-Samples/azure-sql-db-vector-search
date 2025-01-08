## .NET/C# samples

This folder contains samples that demonstrate how to use Native Vector Search in C#/.NET. The Sample solution contains
examples for different use cases, that demonstrate how to work with vectors. Following is the list of use cases implemented in the solution:

1. Create and insert vectors in the SQL table
2. Create and insert embeddings in the SQL table
3. Reading vectors
4. Find Similar vectors
5. Document Classification

To execute the samples, ensure you configure the following environment variables in the `louchSettings.json` file: `ApiKey`, `SqlConnStr` and , `EmbeddingModelName`

~~~json
{
  "profiles": {
    "SqlServer.NativeVectorSearch.Samples": {
      "commandName": "Project",
      "environmentVariables": {
        "ApiKey": "***",
        "EmbeddingModelName": "***",
        "SqlConnStr": "***"
      }
    }
  }
}
~~~

You also need to create the following table (Note: the solution uses the scheme 'test'):   

~~~sql
      CREATE TABLE test.Vectors
        (
          [Id] INT IDENTITY(1,1) NOT NULL,
          [Text] NVARCHAR(MAX) NULL,
          [VectorShort] VECTOR(3)  NULL,
          [Vector] VECTOR(1536)  NULL
       ) ON [PRIMARY];
~~~

### 1. Create and insert vectors in the SQL table
This example (CreateAndInsertVectorsAsync) provides a demonstration of creating vectors and inserting them into a database table. For clarity and simplicity, the example inserts two 3-dimensional vectors.

~~~csharp
  public static async Task CreateAndInsertVectorsAsync()
  {
      using (SqlConnection connection = new SqlConnection(_cConnStr))
      {
          // Vector is inserted in the column '[VectorShort] VECTOR(3)  NULL'
          string sql = $"INSERT INTO [test].[Vectors] ([VectorShort]) VALUES (@Vector)";

          SqlCommand command1 = new SqlCommand(sql, connection);

          // Insert vector as string. Note JSON array.
          command1.Parameters.AddWithValue("@Vector", "[1.12, 2.22, 3.33]");

          SqlCommand command2 = new SqlCommand(sql, connection);

          // Insert vector as JSON string serialized from the float array.
          command2.Parameters.AddWithValue("@Vector", JsonSerializer.Serialize(new float[] { 1.12f, 2.22f, 3.33f }));

          connection.Open();

          var result1 = await command1.ExecuteNonQueryAsync();

          var result2 = await command2.ExecuteNonQueryAsync();

          connection.Close();
      }
~~~

### 2. Create and insert embeddings in the SQL table
This example (CreateAndInsertEmbeddingAsync) illustrates the process of generating an embedding vector from a string using a pre-defined embedding model and 
subsequently inserting the resulting vector into a database table. 
The sample provides a step-by-step approach, highlighting how to utilize the embedding model to transform textual input into 
a high-dimensional vector representation. It further details the process of storing this vector efficiently within a table, ensuring compatibility with advanced search and semantic matching capabilities.

~~~csharp
 public static async Task CreateAndInsertEmbeddingAsync()
 {
     EmbeddingClient client = new(_cEmbeddingModel, _cApiKey);

     // The text to be converted to a vector.
     string text = "Native Vector Search for SQL Server";

     // Generate the embedding vector.
     var res = await client.GenerateEmbeddingsAsync(new List<string>() { text });

     OpenAIEmbedding embedding = res.Value.First();

     ReadOnlyMemory<float> embeddingVector = embedding.ToFloats();

     //
     // Following code demonstrates how to insert the vector into the column Vector:
     // [Vector] VECTOR(1536)  NULL
     using (SqlConnection connection = new SqlConnection(_cConnStr))
     {
         var id = Guid.NewGuid().ToString();

         // Embedding is inserted in the column '[Vector] VECTOR(1536)  NULL'
         SqlCommand command = new SqlCommand($"INSERT INTO [test].[Vectors] ([Vector], [Text]) VALUES ( @Vector, @Text)", connection);

         command.Parameters.AddWithValue("@Vector", JsonSerializer.Serialize(embeddingVector.ToArray()));
         command.Parameters.AddWithValue("@Text", text);

         connection.Open();

         var result = await command.ExecuteNonQueryAsync();

         connection.Close();
     }
 }
~~~

### 3. Reading vectors
This example (ReadVectorsAsync) demonstrates the process of retrieving vectors stored in a database table. 
It provides a step-by-step guide on how to read rows that contain vector columns. The example focuses on best practices for handling vector data, 
including correct casting.

~~~csharp
 public static async Task ReadVectorsAsync()
 {
     List<(long Id, string VectorShort, string Vector, string Text)> rows = new();

     using (SqlConnection connection = new SqlConnection(_cConnStr))
     {
         var id = Guid.NewGuid().ToString();

         SqlCommand command = new SqlCommand($"Select TOP(100) * FROM [test].[Vectors]", connection);

         connection.Open();

         using (SqlDataReader reader = await command.ExecuteReaderAsync())
         {
             while (await reader.ReadAsync())
             {
                 (long Id, string VectorShort, string Vector, string Text) row = new(
                     reader.GetInt32(reader.GetOrdinal("Id")),
                     reader.IsDBNull(reader.GetOrdinal("VectorShort")) ? "-" : reader.GetString(reader.GetOrdinal("VectorShort")),
                     reader.IsDBNull(reader.GetOrdinal("Vector")) ? "-" : reader.GetString(reader.GetOrdinal("Vector")).Substring(0, 20) + "...",
                     reader.IsDBNull(reader.GetOrdinal("Text")) ? "-" : reader.GetString(reader.GetOrdinal("Text"))
                 );

                 rows.Add(row);
             }
         }

         connection.Close();
     }

     foreach (var row in rows)
     {
         Console.WriteLine($"{row.Id}, {row.Vector}, {row.Text}");
     }
 }
~~~

### 4. Find Similar Vectors
The example (FindSimilarAsync) demonstrates how to calculate the distance between vectors and how to look up the top best-matching vectors.

~~~csharp
  public static async Task FindSimilarAsync()
  {
      List<(long Id, double Distance, string Text)> rows = new();

      var embedding = new float[] { 1.12f, 2.22f, 3.33f };

      using (SqlConnection connection = new SqlConnection(_cConnStr))
      {
          var id = Guid.NewGuid().ToString();

          SqlCommand command = new SqlCommand($"Select TOP(100) Id, Text, VECTOR_DISTANCE('cosine', CAST(@Embedding AS Vector(3)), VectorShort) AS Distance FROM [test].[Vectors]", connection);

          command.Parameters.AddWithValue("@Embedding", JsonSerializer.Serialize(embedding));

          connection.Open();

          using (SqlDataReader reader = await command.ExecuteReaderAsync())
          {
              while (await reader.ReadAsync())
              {
                  (long Id, double distance, string Text) row = new(
                      reader.GetInt32(reader.GetOrdinal("Id")),
                      reader.IsDBNull(reader.GetOrdinal("Distance")) ? -999 : reader.GetDouble(reader.GetOrdinal("Distance")),
                      reader.IsDBNull(reader.GetOrdinal("Text")) ? "-" : reader.GetString(reader.GetOrdinal("Text"))
                  );

                  rows.Add(row);
              }
          }

          connection.Close();
      }

      foreach (var row in rows)
      {
          Console.WriteLine($"{row.Id}, {row.Distance}, {row.Text}");
      }
  }
~~~~

### 5. Document Classification
The example (ClassifyDocumentsAsync) presents a high-level scenario to demonstrate the implementation of document classification. 
It begins by generating sample documents of two distinct types: invoices and delivery documents (shipment statements). 
To create test documents for both types, the GenerateTestDocumentsAsync method is utilized, producing 10 simulated invoices and 10 shipment statements. 
Once the documents are generated, the method (ClassifyDocumentsAsync) leverages the embedding model to create corresponding embedding vectors. 
These vectors, along with the associated document text, are then inserted into the database to facilitate further classification and semantic analysis.

