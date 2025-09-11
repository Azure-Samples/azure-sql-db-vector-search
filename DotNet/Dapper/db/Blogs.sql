IF NOT EXISTS (SELECT * FROM sys.tables WHERE object_id = OBJECT_ID(N'[dbo].[Blogs]'))
BEGIN
CREATE TABLE [dbo].[Blogs]
(
    [BlogId] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [Name] NVARCHAR(200) NOT NULL,
    [Url] NVARCHAR(400) NOT NULL
);

CREATE UNIQUE INDEX IX_Blogs_Name ON [dbo].[Blogs]([Name]);
END
