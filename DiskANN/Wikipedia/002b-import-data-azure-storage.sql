-- Uncomment if using SQL Server 2025
-- use WikipediaTest

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
truncate table dbo.[wikipedia_articles_embeddings];
bulk insert dbo.[wikipedia_articles_embeddings]
from 'wikipedia/vector_database_wikipedia_articles_embedded.csv'
with (	
	data_source = 'sample_data',
    format = 'csv',
    firstrow = 2,
    codepage = '65001', 
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
