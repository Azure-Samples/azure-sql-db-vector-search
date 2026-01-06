-- Uncomment if using SQL Server 2025
-- use WikipediaTest

/*
	Import data reading it from a local file. Usable only with SQL Server 2025 
	The file can be downloaded from https://cdn.openai.com/API/examples/data/vector_database_wikipedia_articles_embedded.zip.
	Unzip it and save it in a local folder.
*/
truncate table dbo.[wikipedia_articles_embeddings];
bulk insert dbo.[wikipedia_articles_embeddings]
from 'w:\_temp\vector\embeddings\vector_database_wikipedia_articles_embedded.csv'
with (	
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