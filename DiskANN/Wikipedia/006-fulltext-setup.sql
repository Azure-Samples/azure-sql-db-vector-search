-- Uncomment if using SQL Server 2025
--use WikipediaTest
--go

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

-- Full-text population is asynchronous. On Azure SQL Hyperscale for 25000 rows
-- it typically completes in ~30 seconds. If the count below is < 25000, wait a
-- bit longer and re-run just this SELECT.
waitfor delay '00:00:15'
go

-- Check how many documents have been indexed so far (final count must be 25000)
select count(distinct document_id) 
from sys.dm_fts_index_keywords_by_document(db_id(), object_id('dbo.wikipedia_articles_embeddings'))
go





