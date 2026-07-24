/*
    Fine Food Reviews · 003-hybrid-search
    ---------------------------------------------------
    Three queries, back to back:
        Q1  vector-only    — great at paraphrase, weak at SKUs / brand names
        Q2  full-text only — great at exact matches, weak at paraphrase
        Q3  HYBRID (RRF)   — both. Rows that win in either modality surface.

    Same table, same query, three retrieval strategies. This is the whole point.
*/
-- Uncomment if using SQL Server 2025:
-- use FineFoodReviews;
-- go

set statistics time on;
set statistics io on;
go

-- --------------------------------------------------------------------------
-- Q1 · VECTOR-ONLY  (paraphrase query)
-- --------------------------------------------------------------------------
-- Shopper intent: "smooth flavorful coffee"
-- Reviewers rarely say "smooth" — they say "not bitter", "not burnt", "mellow",
-- "easy on the stomach". Vectors bridge that. BM25 alone would miss most of it.
declare @q1 nvarchar(500) = N'smooth flavorful coffee';
declare @v1 vector(1536)  = ai_generate_embeddings(@q1 use model AIEmbeddings);

select top (10) with approximate
    r.Id,
    r.ProductId,
    r.Score,
    r.Summary,
    left(r.[Text], 120) + iif(len(r.[Text]) > 120, N'…', N'') as text_preview,
    s.distance as cosine_distance
from vector_search(
    table       = dbo.reviews as r,
    column      = embedding,
    similar_to  = @v1,
    metric      = 'cosine'
) as s
order by s.distance;
go


-- --------------------------------------------------------------------------
-- Q2 · FULL-TEXT ONLY  (brand / SKU query)
-- --------------------------------------------------------------------------
-- Shopper intent: "Green Mountain Nantucket Blend" — an exact brand + product name.
-- Vector alone drifts to generic Keurig / coffee reviews.
-- BM25 nails the literal brand + blend match.
select top (10)
    r.Id,
    r.ProductId,
    r.Score,
    r.Summary,
    left(r.[Text], 120) + iif(len(r.[Text]) > 120, N'…', N'') as text_preview,
    ftt.[rank] as bm25_rank
from dbo.reviews r
inner join freetexttable(dbo.reviews, combined, N'Green Mountain Nantucket Blend') ftt
    on r.Id = ftt.[KEY]
order by ftt.[rank] desc;
go

-- --------------------------------------------------------------------------
-- Q3 · HYBRID  (vector + full-text, blended with RRF)
-- --------------------------------------------------------------------------
-- Shopper intent: "Green Mountain blend that is smooth and flavorful" — brand AND paraphrase.
-- Keyword side locks onto "Green Mountain"; vector side finds reviewers writing
-- "not bitter", "mellow", "easy on the stomach". RRF surfaces rows that win in
-- either signal.
declare @q  nvarchar(1000) = N'Green Mountain blend that is smooth and flavorful';
declare @v  vector(1536)   = ai_generate_embeddings(@q use model AIEmbeddings);
declare @k  int            = 20;   -- candidates per signal
declare @rrf_k int          = 60;  -- standard RRF constant

with keyword_search as (
    select top (@k)
        r.Id,
        rank() over (order by ftt.[rank] desc) as keyword_rank
    from dbo.reviews r
    inner join freetexttable(dbo.reviews, combined, @q) ftt
        on r.Id = ftt.[KEY]
    order by ftt.[rank] desc
),
semantic_search as (
    select top (@k)
        s.Id,
        rank() over (order by s.cosine_distance) as vector_rank
    from (
        select top (@k) with approximate
            r.Id,
            s0.distance as cosine_distance
        from vector_search(
            table       = dbo.reviews as r,
            column      = embedding,
            similar_to  = @v,
            metric      = 'cosine'
        ) as s0
        order by s0.distance
    ) s
),
fused as (
    select
        coalesce(ss.Id, ks.Id) as Id,
        ss.vector_rank,
        ks.keyword_rank,
        coalesce(1.0 / (@rrf_k + ss.vector_rank),  0.0) +
        coalesce(1.0 / (@rrf_k + ks.keyword_rank), 0.0) as rrf_score
    from semantic_search ss
    full outer join keyword_search ks on ss.Id = ks.Id
)
select top (7)
    r.Id,
    r.ProductId,
    r.Score,
    r.Summary,
    left(r.[Text], 100) + iif(len(r.[Text]) > 100, N'…', N'') as text_preview,
    rank() over (order by f.rrf_score desc) as rrf_rank,
    f.vector_rank,
    f.keyword_rank,
    cast(f.rrf_score * 1000 as int) as rrf_score_x1000
from fused f
inner join dbo.reviews r on f.Id = r.Id
order by f.rrf_score desc;
go

/*
    Takeaway
    ---------
    Hybrid isn't a library. It's a WITH clause.
    Both indexes live on the same table. No second data store.
    Rerank is one REST call away when relevance beats latency — see
    ../../Semantic-Reranking/02-rerank.sql.
*/
