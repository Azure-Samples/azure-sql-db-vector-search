-- Uncomment if using SQL Server 2025
--use WikipediaTest
--go

set statistics time off
go

select db_id(), @@spid
go

--- Create Indexes 
--- (with 16 vCores, creation time is expected to be 30 seconds for each index)
--- Monitor index creation progress using:
--- select session_id, status, command, percent_complete from sys.dm_exec_requests where session_id = <session id>
create vector index vec_idx on [dbo].[wikipedia_articles_embeddings]([title_vector]) 
with (metric = 'cosine', type = 'diskann'); 
go

create vector index vec_idx2 on [dbo].[wikipedia_articles_embeddings]([content_vector]) 
with (metric = 'cosine', type = 'diskann'); 
go

-- View created vector indexes
select * from sys.vector_indexes
go

-- Enable io statistics
set statistics time on
go

/*
	RUN ANN (Approximate) VECTOR SEARCH
*/
declare @qv vector(1536) = (select v from dbo.wikipedia_search_vectors where id = 1);
select 
	t.id, s.distance, t.title
from
	vector_search(
		table = [dbo].[wikipedia_articles_embeddings] as t, 
		column = [content_vector], 
		similar_to = @qv, 
		metric = 'cosine', 
		top_n = 50
	) as s
order by s.distance, title;
go

/*
	RUN KNN (Exact) VECTOR SEARCH
*/
declare @qv vector(1536) = (select v from dbo.wikipedia_search_vectors where id = 1);
select top (50) id, vector_distance('cosine', @qv, [content_vector]) as distance, title
from [dbo].[wikipedia_articles_embeddings]
order by distance;
go

/*
	Calculate Recall
*/
declare @n int = 100;
declare @qv vector(1536) = (select v from dbo.wikipedia_search_vectors where id = 1);
with cteANN as
(
	select top (@n)
		t.id, s.distance, t.title
	from
		vector_search(
			table = [dbo].[wikipedia_articles_embeddings] as t, 
			column = [content_vector], 
			similar_to = @qv, 
			metric = 'cosine', 
			top_n = @n
		) as s
	order by s.distance, id
),
cteKNN as
(
	select top (@n) id, vector_distance('cosine', @qv, [content_vector]) as distance, title
	from [dbo].[wikipedia_articles_embeddings]
	order by distance, id	
)
select	
	k.id as id_knn,
	a.id as id_ann,
	k.title,
	k.distance as distance_knn,
	a.distance as distance_ann,
	running_recall = cast(cast(count(a.id) over (order by k.distance) as float) 
				/ cast(count(k.id) over (order by k.distance) as float) as decimal(6,3))
from
	cteKNN k
left outer join
	cteANN a on k.id = a.id
order by
	k.distance