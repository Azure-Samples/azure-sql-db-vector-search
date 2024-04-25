drop table if exists dbo.document_embeddings
drop table if exists dbo.documents
go

create table dbo.documents
(
    id int constraint pk__documents primary key,
    content nvarchar(max),
    embedding nvarchar(max)
)
create table dbo.document_embeddings
(
    id int references dbo.documents(id),
    vector_value_id int,
    vector_value float
)
go

create clustered columnstore index csi__document_embeddings 
    on dbo.document_embeddings order (id)
go

if not exists(select * from sys.fulltext_catalogs where [name] = 'FullTextCatalog')
begin
    create fulltext catalog [FullTextCatalog] as default;
end
go

create fulltext index on dbo.documents (content) key index pk__documents;
go

alter fulltext index on dbo.documents enable; 
go

create or alter function dbo.similar_documents(@vector nvarchar(max))
returns table
as
return 
with cteVector as
(
    select
        cast([key] as int) as [vector_value_id],
        cast([value] as float) as [vector_value]
    from
        openjson(@vector)
),
cteSimilar as
(
    select top (50)
        v2.id,
        1-sum(v1.[vector_value] * v2.[vector_value]) / 
        (
            sqrt(sum(v1.[vector_value] * v1.[vector_value])) 
            * 
            sqrt(sum(v2.[vector_value] * v2.[vector_value]))
        ) as cosine_distance
    from
        cteVector v1
    inner join
        dbo.document_embeddings v2 on v1.vector_value_id = v2.vector_value_id
    group by
        v2.id
    order by
        cosine_distance
)
select
    rank() over (order by r.cosine_distance) as rank,
    r.id,
    r.cosine_distance
from
    cteSimilar r
go
