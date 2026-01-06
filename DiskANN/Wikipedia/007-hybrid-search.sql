/*
    Run Hybrid Search using Vector Search and FullText Search and then 
    using Reciprocal Ranking Fusion to calculate the final rank score

    Results are saved into dbo.wikipedia_articles_search_results so that they can be reused
    in the next script
*/
-- Uncomment if using SQL Server 2025
--use WikipediaTest
--go

set statistics time on
set statistics io on
go

drop table if exists dbo.wikipedia_articles_search_results;

declare @q nvarchar(1000), @v vector(1536);
declare @k int = 50;

select @q=q, @v=v from dbo.wikipedia_search_vectors where id = 1;

with keyword_search as (
    select top(@k)
        id, 
        rank() over (order by ft_rank desc) as [rank],
        title,
        [text]
    from
        (
            select top(@k)
                id,
                ftt.[rank] as ft_rank,
                title,
                [text]
            from 
                dbo.wikipedia_articles_embeddings w
            inner join 
                freetexttable(dbo.wikipedia_articles_embeddings, *, @q) as ftt on w.id = ftt.[KEY] -- FREETEXTTABLE returns BM25 rank
            order by
                ft_rank desc
        ) as freetext_documents
    order by
        rank asc
),
semantic_search as
(
    select top(@k)
        id, 
        rank() over (order by cosine_distance) as [rank]
    from
        (
            select top(@k)
	            t.id, s.distance as cosine_distance
            from
	            vector_search(
		            table = [dbo].[wikipedia_articles_embeddings] as t, 
		            column = [content_vector], 
		            similar_to = @v, 
		            metric = 'cosine', 
		            top_n = @k
	        ) as s
            order by cosine_distance
        ) as similar_documents
),
result as (
    select top(@k)
        coalesce(ss.id, ks.id) as id,
        ss.[rank] as semantic_rank,
        ks.[rank] as keyword_rank,
        coalesce(1.0 / (@k + ss.[rank]), 0.0) +
        coalesce(1.0 / (@k + ks.[rank]), 0.0) as score -- Reciprocal Rank Fusion (RRF) 
    from
        semantic_search ss
    full outer join
        keyword_search ks on ss.id = ks.id
    order by 
        score desc
)   
select
    w.id,
    cast(score * 1000 as int) as rrf_score,
    rank() over(order by cast(score * 1000 as int) desc) as rrf_rank,
    semantic_rank,
    keyword_rank,
    w.title,
    w.[text]
into
    dbo.wikipedia_articles_search_results
from
    result as r
inner join
    dbo.wikipedia_articles_embeddings as w on r.id = w.id
order by
    rrf_rank
go

select 
    * 
from 
    dbo.wikipedia_articles_search_results
order by
    rrf_rank