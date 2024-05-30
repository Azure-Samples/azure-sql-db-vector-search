using Microsoft.EntityFrameworkCore;
using System;
using System.Collections.Generic;

namespace EFCoreVectors;

public class BloggingContext : DbContext
{
    public DbSet<Blog> Blogs { get; set; }
    public DbSet<Post> Posts { get; set; }

    protected override void OnConfiguring(DbContextOptionsBuilder optionsBuilder)
    {
        DotNetEnv.Env.Load();

        // Enable vector search
        optionsBuilder.UseSqlServer(
            Environment.GetEnvironmentVariable("MSSQL"),
            o => o.UseVectorSearch()
        );

        //optionsBuilder.LogTo(Console.WriteLine);
    }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        // Configure the float[] property as a vector:
        modelBuilder.Entity<Post>().Property(b => b.Embedding).IsVector();
    }
}

public class Blog
{
    public int BlogId { get; set; }
    public string Name { get; set; } = string.Empty;
    public string Url { get; set; } = string.Empty;
    public List<Post> Posts { get; } = [];   
}

public class Post
{
    public int PostId { get; set; }
    public string Title { get; set; } = string.Empty;
    public string Content { get; set; } = string.Empty;
    public float[] Embedding { get; set; } = [];
    public int BlogId { get; set; }
    public Blog Blog { get; set; } = null!;
}

public class SavedPost {
    public string Title { get; set; } = string.Empty;
    public string Content { get; set; } = string.Empty;
}