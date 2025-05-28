use WikipediaTest
go

if not exists(select * from sys.fulltext_catalogs where [name] = 'FullTextCatalog')
begin
    create fulltext catalog [FullTextCatalog] as default;
end
go

create fulltext index on dbo.wikipedia_articles_embeddings ([text]) key index pk__wikipedia_articles_embeddings;
go

alter fulltext index on dbo.wikipedia_articles_embeddings enable; 
go

select * from sys.fulltext_catalogs
go

-- Wait ~15 seconds for FT to start and process all the documents, then

-- Check how many documents have been indexed so far
select count(distinct document_id) 
from sys.dm_fts_index_keywords_by_document(db_id(), object_id('dbo.wikipedia_articles_embeddings'))
go





