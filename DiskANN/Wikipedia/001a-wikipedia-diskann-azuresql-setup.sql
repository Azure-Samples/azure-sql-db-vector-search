/*
	This script requires Azure SQL DB
*/

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

/*
	Cleanup if needed
*/
if not exists(select * from sys.symmetric_keys where [name] = '##MS_DatabaseMasterKey##')
begin
	create master key encryption by password = 'Pa$$w0rd!'
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
	Create database scoped credential and external data source.
	
	File taken from https://cdn.openai.com/API/examples/data/vector_database_wikipedia_articles_embedded.zip

	File is assumed to be in a path like: https://<myaccount>.blob.core.windows.net/sample-data/wikipedia/vector_database_wikipedia_articles_embedded.csv

	Please note that it is recommened to avoid using SAS tokens: the best practice is to use Managed Identity as described here:
	https://learn.microsoft.com/en-us/sql/relational-databases/import-export/import-bulk-data-by-using-bulk-insert-or-openrowset-bulk-sql-server?view=sql-server-ver16#bulk-importing-from-azure-blob-storage
*/
create database scoped credential [sample_data]
with identity = 'Managed Identity'
go
create external data source [sample_data]
with 
( 
	type = blob_storage,
 	location = 'https://dmstore2.blob.core.windows.net/sample-data/',
	credential = [sample_data]
);
go

/*
	Import data
*/
bulk insert dbo.[wikipedia_articles_embeddings]
from 'wikipedia/vector_database_wikipedia_articles_embedded.csv'
with (	
	data_source = 'sample_data',
    format = 'csv',
    firstrow = 2,
    codepage = '65001', --comment if using MSSQL on Linux
	fieldterminator = ',',
	rowterminator = '0x0a',
    fieldquote = '"',
    batchsize = 1000,
    tablock
)
go
select row_count from sys.dm_db_partition_stats 
where object_id = OBJECT_ID('[dbo].[wikipedia_articles_embeddings]') and index_id in (0, 1)
go

/*
	Add primary key
*/
alter table [dbo].[wikipedia_articles_embeddings]
add constraint pk__wikipedia_articles_embeddings primary key clustered (id)
go

/*
	Add index on title
*/
create index [ix_title] on [dbo].[wikipedia_articles_embeddings](title)
go

/*
	Verify data
*/
select top (10) * from [dbo].[wikipedia_articles_embeddings]
go

select *,
	DATALENGTH(content_vector) as bytes, 
	DATALENGTH(CAST(content_vector as varchar(max))) as chars
from 
	[dbo].[wikipedia_articles_embeddings] where title like 'Philosoph%'
go
