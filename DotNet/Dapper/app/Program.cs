using System.Text.Json;
using Dapper;
using DotNetEnv;
using Microsoft.Data.SqlClient;
using Microsoft.Data.SqlTypes;
using DapperVectors;

// Load .env
Env.Load();

// Update Dapper Type Handler to handle SqlVector<T>
SqlMapper.AddTypeHandler(new VectorTypeHandler());

// Get connection string from environment variable
var connectionString = Environment.GetEnvironmentVariable("MSSQL");
if (string.IsNullOrWhiteSpace(connectionString))
{
    Console.WriteLine("Please set the MSSQL environment variable (for example in a .env file). Exiting.");
    return;
}

// Create SQL connection
Console.WriteLine("Connecting to database...");
await using var connection = new SqlConnection(connectionString);

// Confirm database project objects exist
var tableExists = await connection.ExecuteScalarAsync<int?>(
    "SELECT COUNT(*) FROM sys.tables WHERE (name = 'Blogs' or name = 'Posts') AND schema_id = SCHEMA_ID('dbo')");

if (tableExists.GetValueOrDefault() != 2)
{
    Console.WriteLine("The database schema does not appear to be deployed. Please publish the database project in the `db` folder before running this sample.");
    return;
}

// Ensure Sample blog exists
const string sampleBlogName = "Sample blog";
var blogId = await connection.QuerySingleOrDefaultAsync<int?>(
    "SELECT BlogId FROM dbo.Blogs WHERE Name = @Name", new { Name = sampleBlogName });

if (!blogId.HasValue)
{
    Console.WriteLine("Creating 'Sample blog'...");    
    blogId = await connection.ExecuteScalarAsync<int>(
        "INSERT INTO dbo.Blogs (Name, Url) OUTPUT INSERTED.BlogId VALUES (@Name, @Url)",
        new { Name = sampleBlogName, Url = "https://devblogs.microsoft.com" }
    );
}

// Choose real or mock embedding client
Console.WriteLine("Creating embedding client...");
var embeddingClient = new AzureOpenAIEmbeddingClient();
// var embeddingClient = new MockEmbeddingClient();

Console.WriteLine("Adding posts...");
var content = File.ReadAllText("content.json");
var newPosts = JsonSerializer.Deserialize<List<SavedPost>>(content)!;
foreach (var np in newPosts)
{
    // compute embedding
    var vector = embeddingClient.GetEmbedding(np.Content);

    // check if post exists for this blog
    var existingPostId = await connection.QuerySingleOrDefaultAsync<int?>(
        "SELECT PostId FROM dbo.Posts WHERE BlogId = @BlogId and Title = @Title",
        new { BlogId = blogId, Title = np.Title });

    if (existingPostId.HasValue)
    {
        await connection.ExecuteAsync(
            "UPDATE dbo.Posts SET Content = @Content, Embedding = @Embedding WHERE PostId = @PostId",
            new { np.Content, Embedding = vector, PostId = existingPostId.Value }
        );
    }
    else
    {
        await connection.ExecuteAsync(
            "INSERT INTO dbo.Posts (Title, Content, Embedding, BlogId) VALUES (@Title, @Content, @Embedding, @BlogId)",
            new { np.Title, np.Content, Embedding = vector, BlogId = blogId }
        );
    }
}

// Query for similar posts
Console.WriteLine("\n----------\n");
string searchPhrase = "I want to use Azure SQL, Dapper and vectors in my app!";
Console.WriteLine($"Search phrase is: '{searchPhrase}'...");

var queryVector = embeddingClient.GetEmbedding(searchPhrase);

var sql = @"
SELECT TOP (5) p.Title,
       VECTOR_DISTANCE('cosine', p.Embedding, @vector) AS Distance
FROM dbo.Posts p
JOIN dbo.Blogs b ON p.BlogId = b.BlogId
WHERE b.Name = @BlogName
ORDER BY Distance ASC;";

var results = await connection.QueryAsync(sql, new { vector = queryVector, BlogName = sampleBlogName });

Console.WriteLine("Similar posts found:");
foreach (var r in results)
{
    Console.WriteLine($"Post: {r.Title}, Distance: {r.Distance}");
}
