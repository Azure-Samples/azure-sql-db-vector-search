/*
    Prepare database to use the Vectorizer:

    https://github.com/Azure-Samples/azure-sql-db-vectorizer

    to vectorize all the existing text in the database
*/
drop table if exists [dbo].[wa];
drop table if exists [dbo].[wa_text_embeddings];
go

select [id], [url], [title], [text] 
into [dbo].[wa]
from [dbo].[wikipedia_articles_embeddings]
go

alter table [dbo].[wa]
add constraint pk__wa primary key clustered (id)
go

select * from [dbo].[wa] where title = 'Alan Turing'
go

select top(10) * from [dbo].[wa_text_embeddings]
go

select * from [dbo].[wa] where id = 1
go

create view dbo.vw_test
as
select [id], [parent_id], [chunk_text], [text_te3s] from  [dbo].[wa_text_embeddings]
go