using Microsoft.Extensions.VectorData;
using Microsoft.SemanticKernel;
using Kernel = Microsoft.SemanticKernel.Kernel;
using Microsoft.SemanticKernel.Connectors.SqlServer;
using Microsoft.SemanticKernel.Embeddings;
using System.Text.Json;
using DotNetEnv;

#pragma warning disable SKEXP0001, SKEXP0010, SKEXP0020, CS8620

Env.Load();

// Get parameters from environment
string azureOpenAIEndpoint = Env.GetString("AZURE_OPENAI_ENDPOINT")!;
string azureOpenAIApiKey = Env.GetString("AZURE_OPENAI_API_KEY")!;
string embeddingModelDeploymentName = Env.GetString("AZURE_OPENAI_EMBEDDING_MODEL")!;
string connectionString = Env.GetString("AZURE_SQL_CONNECTION_STRING")!;

// Sample Data
var glossaryEntries = new List<Glossary>()
{
    new()
    {
        Key = 1,
        Term = "API",
        Definition = "Application Programming Interface. A set of rules and specifications that allow software components to communicate and exchange data."
    },
    new()
    {
        Key = 2,
        Term = "Connectors",
        Definition = "Connectors allow you to integrate with various services provide AI capabilities, including LLM, AudioToText, TextToAudio, Embedding generation, etc."
    },
    new()
    {
        Key = 3,
        Term = "RAG",
        Definition = "Retrieval Augmented Generation - a term that refers to the process of retrieving additional data to provide as context to an LLM to use when generating a response (completion) to a user's question (prompt)."
    }
};

/*
 * Set up Semantic Kernel
 */
Console.WriteLine("Creating Semantic Kernel services...");

// Build the kernel and configure the embedding provider
var builder = Kernel.CreateBuilder();
builder.AddAzureOpenAITextEmbeddingGeneration(embeddingModelDeploymentName, azureOpenAIEndpoint, azureOpenAIApiKey);
var kernel = builder.Build();

// Define vector store
var vectorStore = new SqlServerVectorStore(connectionString);

// Get a collection instance using vector store
// IMPORTANT: Make sure the use the same data type for key here and for the VectorStoreRecordKey element
var collection = vectorStore.GetCollection<int, Glossary>("SemanticKernel_VectorStore");
await collection.CreateCollectionIfNotExistsAsync();

// Get embedding service
var textEmbeddingGenerationService = kernel.GetRequiredService<ITextEmbeddingGenerationService>();

/*
 * Generate embeddings for each glossary item
 */
Console.WriteLine("\nGenerating embeddings...");

var tasks = glossaryEntries.Select(entry => Task.Run(async () =>
{    
    entry.DefinitionEmbedding = await textEmbeddingGenerationService.GenerateEmbeddingAsync(entry.Definition);
}));

await Task.WhenAll(tasks);

/*
 * Upsert the data into the vector store
 */
Console.WriteLine("\nUpserting data into vector store...");

await foreach (var key in collection.UpsertBatchAsync(glossaryEntries))
{
    Console.WriteLine(key);
}

/*
 * Upsert the data into the vector store
 */
Console.WriteLine("\nReturn the inserted data...");

var options = new GetRecordOptions() { IncludeVectors = false };

await foreach (var record in collection.GetBatchAsync(keys: [1, 2, 3], options))
{
    Console.WriteLine($"Key: {record.Key}");
    Console.WriteLine($"Term: {record.Term}");
    Console.WriteLine($"Definition: {record.Definition}");
}

/*
 * Upsert the data into the vector store
 */
Console.WriteLine("\nRun vector search...");

var searchString = "I want to learn more about Connectors";

Console.WriteLine($"Search string: '{searchString}'");

var searchVector = await textEmbeddingGenerationService.GenerateEmbeddingAsync(searchString);
var searchResult = await collection.VectorizedSearchAsync(searchVector);

Console.WriteLine($"Results:");

await foreach (var result in searchResult.Results)
{
    Console.WriteLine($"Search score: {result.Score}");
    Console.WriteLine($"Key: {result.Record.Key}");
    Console.WriteLine($"Term: {result.Record.Term}");
    Console.WriteLine($"Definition: {result.Record.Definition}");
    Console.WriteLine("=========");
}

public sealed class Glossary
{
    [VectorStoreRecordKey]
    public int Key { get; set; }

    [VectorStoreRecordData]
    public string? Term { get; set; }

    [VectorStoreRecordData]
    public string? Definition { get; set; }

    [VectorStoreRecordVector(Dimensions: 1536)]
    public ReadOnlyMemory<float> DefinitionEmbedding { get; set; }
}