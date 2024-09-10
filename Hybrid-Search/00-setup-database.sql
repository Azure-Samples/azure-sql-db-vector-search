drop table if exists dbo.documents
go

create table dbo.documents
(
    id int constraint pk__documents primary key,
    content nvarchar(max),
    embedding vector(384)
)

if not exists(select * from sys.fulltext_catalogs where [name] = 'FullTextCatalog')
begin
    create fulltext catalog [FullTextCatalog] as default;
end
go

create fulltext index on dbo.documents (content) key index pk__documents;
go

alter fulltext index on dbo.documents enable; 
go
