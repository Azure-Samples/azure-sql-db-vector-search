using System;
using System.Linq;
using Azure;
using Azure.AI.OpenAI;
using EFCore.SqlServer.VectorSearch;
using DotNetEnv;
using Microsoft.EntityFrameworkCore;

Env.Load();

// Create EF Core context
using var db = new BloggingContext();

// Create

Console.WriteLine("Getting sample blog...");
var blog = db.Blogs
    .Where(b => b.Name == "Sample blog")
    .FirstOrDefault();

if (blog == null) {
    Console.WriteLine("Creating 'Sample blog'...");
    blog = new Blog { Name = "Sample blog", Url = "https://devblogs.microsoft.com" };
    db.Add(blog);
    db.SaveChanges();
}

// Add posts
Console.WriteLine("Adding posts...");
var posts = new List<Post>() {
    new() { 
        Title = "Hello World", 
        Content = "I wrote an app using EF Core!",        
    },
    new() { 
        Title = "Vectors with Azure SQL and EF Core", 
        Content = "You can use and store vectors easily Azure SQL and EF Core", 
    },
    new() { 
        Title = "EFCore.SqlServer.VectorSearch in PreRelease", 
        Content = "The NuGet package EFCore.SqlServer.VectorSearch is now available in PreRelease! With this package you can use vector search functions in your LINQ queries.",         
    }
};

// Console.WriteLine("Adding embeddings...");
var embeddingClient = new AzureOpenAIEmbeddingClient();

posts.ForEach(post => {
    post.Embedding = embeddingClient.GetEmbedding(post.Content);
});

// Adding posts to database
posts.ForEach(post => {
    var p = blog.Posts.Where(p => p.Title == post.Title).FirstOrDefault();
    if (p == null) {
        blog.Posts.Add(post);
    } else  {
        p.Title = post.Title;
        p.Content = post.Content;
        p.Embedding = post.Embedding;
    }
});
db.SaveChanges();

// Find similar post
Console.WriteLine("\n----------\n");

// Querying
string searchPhrase = "I want to use Azure SQL, EF Core and vectors in my app!";
Console.WriteLine($"Search phrase is: '{searchPhrase}'...");
Console.WriteLine("Querying for similar posts...");
float[] vector = embeddingClient.GetEmbedding(searchPhrase);
var relatedPosts = await db.Posts
    .Where(p => p.Blog.Name == "Sample Blog")
    .OrderBy(p => EF.Functions.VectorDistance("cosine", p.Embedding, vector))
    .Take(2)
    .ToListAsync();

relatedPosts.ForEach(p => {
    Console.WriteLine($"Post: {p.Title}");
});

