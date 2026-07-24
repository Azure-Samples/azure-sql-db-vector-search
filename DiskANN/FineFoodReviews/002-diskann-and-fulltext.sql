/*
    Fine Food Reviews · 002-diskann-and-fulltext
    ---------------------------------------------------------
    Builds the two indexes hybrid search needs:
      1. DiskANN vector index on dbo.reviews(embedding)          — for VECTOR_SEARCH
      2. Full-text catalog + index on dbo.reviews(combined)      — for FREETEXTTABLE

    Both indexes live on the same table. No data movement.
*/
-- Uncomment if using SQL Server 2025:
-- use FineFoodReviews;
-- go

-- ==========================================================================
-- 1 · DiskANN vector index
-- ==========================================================================
if exists (
    select 1
    from sys.indexes
    where object_id = object_id(N'dbo.reviews') and name = N'vec_idx_reviews'
)
    drop index vec_idx_reviews on dbo.reviews;
go

create vector index vec_idx_reviews
on dbo.reviews (embedding)
with (
    metric = 'cosine',
    type   = 'diskann'
);
go

-- Verify
select
    i.name         as index_name,
    v.build_parameters,
    json_value(v.build_parameters, '$.Version') as index_version
from sys.vector_indexes v
join sys.indexes i on v.object_id = i.object_id and v.index_id = i.index_id
where v.object_id = object_id(N'dbo.reviews');
go

-- ==========================================================================
-- 2 · Full-text catalog + index on combined (Summary + ': ' + Text)
-- ==========================================================================
if exists (select 1 from sys.fulltext_catalogs where name = N'ft_reviews_catalog')
begin
    if exists (
        select 1 from sys.fulltext_indexes
        where object_id = object_id(N'dbo.reviews')
    )
        drop fulltext index on dbo.reviews;

    drop fulltext catalog ft_reviews_catalog;
end;
go

create fulltext catalog ft_reviews_catalog as default;
go

create fulltext index on dbo.reviews (combined language 1033)
    key index PK_reviews  -- named explicitly in 000-setup.sql
    on ft_reviews_catalog
    with change_tracking auto;
go

-- Wait for population (500 rows populates in ~10s). Verify:
-- 0 = idle (populated); non-zero = still crawling.
select
    fulltextcatalogproperty(N'ft_reviews_catalog', 'PopulateStatus') as populate_status,
    fulltextcatalogproperty(N'ft_reviews_catalog', 'ItemCount')      as item_count;
go

-- Smoke test full-text: how many reviews mention "oatmeal"?
select count(*) as oatmeal_mentions
from dbo.reviews
where contains(combined, N'oatmeal');
go

print N'Indexes ready. Next: 003-hybrid-search.sql';
