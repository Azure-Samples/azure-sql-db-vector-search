/*
	This script requires SQL Server 2025 RC0
*/

create database WikipediaTest
go

use WikipediaTest
go

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
	Import data. File taken from 
    https://cdn.openai.com/API/examples/data/vector_database_wikipedia_articles_embedded.zip
*/
bulk insert dbo.[wikipedia_articles_embeddings]
from 'C:\samples\rc0\datasets\vector_database_wikipedia_articles_embedded.csv'
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

select * from [dbo].[wikipedia_articles_embeddings] where title like 'Philosoph%'
go
