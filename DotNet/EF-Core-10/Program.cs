using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using DotNetEnv;
using EFCoreVectors;
using Microsoft.Data.SqlTypes;

// Load .env
Env.Load();

// Create EF Core context
using var db = new BloggingContext();

// Create blog
Console.WriteLine("Getting sample blog...");
var blog = db.Blogs
    .Include(blog => blog.Posts)
    .FirstOrDefault(b => b.Name == "Sample blog");

if (blog == null) {
    Console.WriteLine("Creating 'Sample blog'...");
    blog = new Blog { Name = "Sample blog", Url = "https://devblogs.microsoft.com" };
    db.Add(blog);
    db.SaveChanges();
}

// Add posts
Console.WriteLine("Adding posts...");
var content = File.ReadAllText("content.json");
var newPosts = JsonSerializer.Deserialize<List<SavedPost>>(content)!;

// Console.WriteLine("Adding embeddings...");
var embeddingClient = new AzureOpenAIEmbeddingClient();
//var embeddingClient = new MockEmbeddingClient();

newPosts.ForEach(np => {
    var p = blog.Posts.FirstOrDefault(p => p.Title == np.Title);
    if (p == null) {
        blog.Posts.Add(new Post { 
            Title = np.Title, 
            Content = np.Content,
            Embedding = new SqlVector<float>(embeddingClient.GetEmbedding(np.Content))
        });
    } else  {
        p.Title = np.Title;
        p.Content = np.Content;
        p.Embedding = new SqlVector<float>(embeddingClient.GetEmbedding(np.Content));
    }
});

// Adding posts to database
db.SaveChanges();

// Find similar post
Console.WriteLine("\n----------\n");

// Querying
string searchPhrase = "I want to use Azure SQL, EF Core and vectors in my app!";
Console.WriteLine($"Search phrase is: '{searchPhrase}'...");

Console.WriteLine("Querying for similar posts...");
var vector = new SqlVector<float>(embeddingClient.GetEmbedding(searchPhrase));
var relatedPosts = await db.Posts
    .Where(p => p.Blog.Name == "Sample Blog")    
    .OrderBy(p => EF.Functions.VectorDistance("cosine", p.Embedding, vector))
    .Select(p => new { p.Title, Distance = EF.Functions.VectorDistance("cosine", p.Embedding, vector) })
    .Take(5)
    .ToListAsync();

Console.WriteLine("Similar posts found:");
relatedPosts.ForEach(rp => {
    Console.WriteLine($"Post: {rp.Title}, Distance: {rp.Distance}");
});

