-- Uncomment if using SQL Server 2025
--use WikipediaTest
--go


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
select top(10) 
	*,
	DATALENGTH(content_vector) as bytes, 
	DATALENGTH(CAST(content_vector as varchar(max))) as chars
from 
	[dbo].[wikipedia_articles_embeddings] where title like 'Philosoph%'
go
