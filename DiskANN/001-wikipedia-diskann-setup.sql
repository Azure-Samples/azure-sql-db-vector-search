/*
	This script requires SQL Server 2025
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
	[title_vector] [varchar](max) not null,
	[content_vector] [varchar](max) not null,
	[vector_id] [int] not null
)
go

/*
	Import data. File taken from 
    https://cdn.openai.com/API/examples/data/vector_database_wikipedia_articles_embedded.zip
*/
bulk insert dbo.[wikipedia_articles_embeddings]
from 'W:\sql-server-2025\samples\azure-sql-db-vector-search\vector_database_wikipedia_articles_embedded.csv'
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
select row_count from sys.dm_db_partition_stats where object_id = OBJECT_ID('[dbo].[wikipedia_articles_embeddings]')
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

select * from [dbo].[wikipedia_articles_embeddings] where title = 'Alan Turing'
go

/*
    Add columns to store the native vectors
*/
alter table wikipedia_articles_embeddings
add title_vector_ada2 vector(1536);

alter table wikipedia_articles_embeddings
add content_vector_ada2 vector(1536);
go

/*
    Update the native vectors
*/
update 
    wikipedia_articles_embeddings
set 
    title_vector_ada2 = cast(title_vector as vector(1536)),
    content_vector_ada2 = cast(content_vector as vector(1536))
go

/*
    Remove old columns
*/
alter table wikipedia_articles_embeddings
drop column title_vector;
go

alter table wikipedia_articles_embeddings
drop column content_vector;
go

/*
	Verify data
*/
select top (10) * from [dbo].[wikipedia_articles_embeddings]
go

select * from [dbo].[wikipedia_articles_embeddings] where title = 'Alan Turing'
go
