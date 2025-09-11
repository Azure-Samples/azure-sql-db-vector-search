IF NOT EXISTS (SELECT * FROM sys.tables WHERE object_id = OBJECT_ID(N'[dbo].[Posts]'))
BEGIN
CREATE TABLE [dbo].[Posts]
(
    [PostId] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [Title] NVARCHAR(400) NOT NULL,
    [Content] NVARCHAR(MAX) NOT NULL,
    [Embedding] VECTOR(1536) NOT NULL,
    [BlogId] INT NOT NULL
);

ALTER TABLE [dbo].[Posts] ADD CONSTRAINT FK_Posts_Blogs_BlogId FOREIGN KEY (BlogId) REFERENCES dbo.Blogs(BlogId);
CREATE UNIQUE INDEX IX_Posts_Title ON [dbo].[Posts]([Title]);
END
