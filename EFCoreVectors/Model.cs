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
        optionsBuilder.UseSqlServer(Environment.GetEnvironmentVariable("MSSQL"));
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
    public string Name { get; set; }
    public string Url { get; set; }
    public List<Post> Posts { get; } = new();
}

public class Post
{
    public int PostId { get; set; }
    public string Title { get; set; }
    public string Content { get; set; }
    public float[] Embedding { get; set; }
    public int BlogId { get; set; }
    public Blog Blog { get; set; }
}