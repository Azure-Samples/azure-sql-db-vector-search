CREATE TABLE [dbo].[Posts]
(
    [PostId] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [Title] NVARCHAR(400) NOT NULL,
    [Content] NVARCHAR(MAX) NOT NULL,
    [Embedding] VECTOR(1536) NOT NULL,
    [BlogId] INT NOT NULL
);
GO

ALTER TABLE [dbo].[Posts] ADD CONSTRAINT FK_Posts_Blogs_BlogId FOREIGN KEY (BlogId) REFERENCES dbo.Blogs(BlogId);
GO

CREATE UNIQUE INDEX IX_Posts_Title ON [dbo].[Posts]([Title]);
GO