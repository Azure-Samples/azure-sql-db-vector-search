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

### 2. Create and insert embeddings in the SQL table
This example (CreateAndInsertEmbeddingAsync) illustrates the process of generating an embedding vector from a string using a pre-defined embedding model and 
subsequently inserting the resulting vector into a database table. 
The sample provides a step-by-step approach, highlighting how to utilize the embedding model to transform textual input into 
a high-dimensional vector representation. It further details the process of storing this vector efficiently within a table, ensuring compatibility with advanced search and semantic matching capabilities.

### 3. Reading vectors
This example (ReadVectorsAsync) demonstrates the process of retrieving vectors stored in a database table. 
It provides a step-by-step guide on how to read rows that contain vector columns. The example focuses on best practices for handling vector data, 
including correct casting.

### 4. Find Similar Vectors
The example (FindSimilarAsync) demonstrates how to calculate the distance between vectors and how to look up the top best-matching vectors.

### 5. Document Classification
The example (ClassifyDocumentsAsync) presents a high-level scenario to demonstrate the implementation of document classification. 
It begins by generating sample documents of two distinct types: invoices and delivery documents (shipment statements). 
To create test documents for both types, the GenerateTestDocumentsAsync method is utilized, producing 10 simulated invoices and 10 shipment statements. 
Once the documents are generated, the method (ClassifyDocumentsAsync) leverages the embedding model to create corresponding embedding vectors. 
These vectors, along with the associated document text, are then inserted into the database to facilitate further classification and semantic analysis.

