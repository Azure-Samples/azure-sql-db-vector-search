-- Uncomment if using SQL Server 2025
--use WikipediaTest
--go

/*
	Cleanup if needed
*/
if not exists(select * from sys.symmetric_keys where [name] = '##MS_DatabaseMasterKey##')
begin
	create master key encryption by password = 'VERY_(Str0nG)_Pa$$w0rd!'
end
go
if exists(select * from sys.[external_data_sources] where name = 'sample_data')
begin
	drop external data source [sample_data];
end
go
if exists(select * from sys.[database_scoped_credentials] where name = 'sample_data')
begin
	drop database scoped credential [sample_data];
end
go

/*
	Create table
*/
drop table if exists [dbo].[wikipedia_articles_embeddings];
create table [dbo].[wikipedia_articles_embeddings]
(
	[id] [int] not null,
	[url] [varchar](1000) not null,
	[title] [varchar](1000) not null,
	[text] [varchar](max) not null,
	[title_vector] [vector](1536) not null,
	[content_vector] [vector](1536) not null,
	[vector_id] [int] not null
)
go
