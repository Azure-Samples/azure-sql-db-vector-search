using Microsoft.Data.SqlTypes;

namespace DapperVectors;

public class Blog
{
    public int BlogId { get; set; }
    public string Name { get; set; } = string.Empty;
    public string Url { get; set; } = string.Empty;
}

public class Post
{
    public int PostId { get; set; }
    public string Title { get; set; } = string.Empty;
    public string Content { get; set; } = string.Empty;
    // We'll use SqlVector<float> to represent the SQL Server vector type when passing to SqlClient
    public SqlVector<float>? Embedding { get; set; }
    public int BlogId { get; set; }
}

public record SavedPost
{
    public string Title { get; init; } = string.Empty;
    public string Content { get; init; } = string.Empty;
}
