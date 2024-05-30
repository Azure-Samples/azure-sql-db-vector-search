using System;
using System.Linq;
using Azure;
using Azure.AI.OpenAI;
using EFCore.SqlServer.VectorSearch;
using DotNetEnv;
using Microsoft.EntityFrameworkCore;
using EFCoreVectors;

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
var newPosts = new List<(string Title, string Content)>() {
    new() { 
        Title = "My first EF Core app!", 
        Content = "I wrote an app using EF Core!",        
    },
    new() { 
        Title = "Vectors with Azure SQL and EF Core", 
        Content = "You can use and store vectors easily Azure SQL and EF Core", 
    },
    new() { 
        Title = "EFCore.SqlServer.VectorSearch in PreRelease", 
        Content = "The NuGet package EFCore.SqlServer.VectorSearch is now available in PreRelease! With this package you can use vector search functions in your LINQ queries.",         
    },
    new() { 
        Title = "SQL Server Best Practices", 
        Content = "Here are some best practices for using SQL Server in your applications.",        
    },
    new() { 
        Title = "Python and Flask", 
        Content = "Learn how to build a web app using Python and Flask!",        
    },
    new() { 
        Title = "Django for REST APIs", 
        Content = "Create a REST API using Django!",        
    },
    new() { 
        Title = "JavaScript for Beginners", 
        Content = "Learn JavaScript from scratch!",        
    },
    new() { 
        Title = "Node vs Rust", 
        Content = "Which one should you choose for your next project?",        
    },
    new() { 
        Title = "Pizza or Focaccia?", 
        Content = "What's the difference between pizza and focaccia. Learn everything you need to know!",        
    },
    new() { 
        Title = "Chocolate Eggs for your next dessert", 
        Content = "Try this delicious recipe for chocolate eggs!",        
    },
};

// Console.WriteLine("Adding embeddings...");
var embeddingClient = new AzureOpenAIEmbeddingClient();
//var embeddingClient = new MockEmbeddingClient();

newPosts.ForEach(np => {
    var p = blog.Posts.FirstOrDefault(p => p.Title == np.Title);
    if (p == null) {
        blog.Posts.Add(new Post { 
            Title = np.Title, 
            Content = np.Content,
            Embedding = embeddingClient.GetEmbedding(np.Content)
        });
    } else  {
        p.Title = np.Title;
        p.Content = np.Content;
        p.Embedding = embeddingClient.GetEmbedding(np.Content);
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
float[] vector = embeddingClient.GetEmbedding(searchPhrase);
var relatedPosts = await db.Posts
    .Where(p => p.Blog.Name == "Sample Blog")    
    .OrderBy(p => EF.Functions.VectorDistance("cosine", p.Embedding, vector))
    .Select(p => new { p.Title, Distance = EF.Functions.VectorDistance("cosine", p.Embedding, vector)})
    .Take(5)    
    .ToListAsync();

Console.WriteLine("Similar posts found:");
relatedPosts.ForEach(rp => {
    Console.WriteLine($"Post: {rp.Title}, Distance: {rp.Distance}");
});

