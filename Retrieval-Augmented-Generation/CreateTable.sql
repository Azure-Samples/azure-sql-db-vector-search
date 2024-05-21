CREATE TABLE [dbo].[embeddings]
(
    [Id] [bigint] NULL,
    [ProductId] [nvarchar](500) NULL,
    [UserId] [nvarchar](50) NULL,
    [Score] [bigint] null,
    [Summary] [nvarchar](max) NULL,
    [Text] [nvarchar](max) NULL,
    [Combined] [nvarchar](max) NULL,
    [Vector] [varbinary](8000) NULL
) 
GO
