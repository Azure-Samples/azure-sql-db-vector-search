/*
    Prepare database to use the Vectorizer:

    https://github.com/Azure-Samples/azure-sql-db-vectorizer

    to vectorize all the existing text in the database
*/
drop table if exists [dbo].[wikipedia_articles];
drop table if exists [dbo].[wikipedia_articles_text_embeddings];
go

select [id], [url], [title], [text] 
into [dbo].[wikipedia_articles]
from [dbo].[wikipedia_articles_embeddings]
go

alter table [dbo].[wikipedia_articles]
add constraint pk__wikipedia_articles primary key clustered (id)
go

select * from [dbo].[wikipedia_articles] where title = 'Alan Turing'
go

-- Run the Database Vectorizer tool
-- to generate embeddings and store them into the [dbo].[wa_text_embeddings] table.

select top(10) * from [dbo].[wikipedia_articles_text_embeddings]
order by parent_id
go

select * from [dbo].[wikipedia_articles_text_embeddings] where id = 1
go

select parent_id, count(*) from [dbo].[wikipedia_articles_text_embeddings] group by parent_id having count(*) > 1
go

select * from [dbo].[wikipedia_articles_text_embeddings] where parent_id = 3796
order by id
go
