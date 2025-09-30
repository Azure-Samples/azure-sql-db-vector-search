drop table if exists dbo.[SqlBulkCopyEmbedding];
create table dbo.[SqlBulkCopyEmbedding]
(
    Id int,
    Embedding vector(1536),
    [Description] nvarchar(max)
)
go

-- Run the SqlBulkCopySample then
select * from dbo.[SqlBulkCopyEmbedding]
go

