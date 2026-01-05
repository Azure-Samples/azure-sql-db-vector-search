/*
    Test the new helf-precision support for vectors
	By converting existing single-precision vectors to half-precision vectors
	and then do a test run using both to see if there are any differences in the outcome
*/
use WikipediaTest
go

-- Enable preview_features configuration for vector index features
alter database scoped configuration
set preview_features = on;
go
select * from sys.database_scoped_configurations where [name] = 'preview_features'
go

-- Add half-precision vector column
alter table [dbo].[wikipedia_articles_embeddings]
add content_vector_fp16 vector(1536, float16)
go

-- View the metadata
select 
	[name] AS column_name,
    system_type_id,
    user_type_id,
    vector_dimensions,
    vector_base_type,
    vector_base_type_desc
from 
	sys.columns 
where 
	object_id = object_id('[dbo].[wikipedia_articles_embeddings]')
go

-- Remove existing vector indexes
select * from sys.vector_indexes
go
drop index if exists vec_idx on [dbo].[wikipedia_articles_embeddings]
drop index if exists vec_idx2 on [dbo].[wikipedia_articles_embeddings]
go
select * from sys.vector_indexes
go

-- Copy the exiting single-precision embeddings to half-precision vector column
update [dbo].[wikipedia_articles_embeddings]
--set content_vector_fp16 = cast(content_vector as vector(1536, float16)) -- Not working at the moment
set content_vector_fp16 = cast(cast(content_vector as json) as vector(1536, float16))
go

-- View different storage space for single-precision (fp32) vs half-precision (fp16) floating point vector
select 
	id, title,
	DATALENGTH(content_vector) as fp32_bytes, 
	DATALENGTH(content_vector_fp16) as fp16_bytes
from 
	[dbo].[wikipedia_articles_embeddings] where title like 'Philosoph%'
go

-- Generate query embeddings
drop table if exists #t;
create table #t (id int, q nvarchar(max), v32 vector(1536, float32), v16 vector(1536, float16))

insert into #t (id, q, v32)
select 
	id, q,  ai_generate_embeddings(q use model Ada2Embeddings)
from
	(values 
		(1, N'four legged furry animal'),
		(2, N'pink floyd music style')
	) S(id, q)
go
update #t set v16 = cast(cast(v32 as json) as vector(1536, float16));
select * from  #t
go

-- Create vector index of single-precision vectors
-- Should take ~30 seconds on a 16 vCore server
create vector index vec_idx32 on [dbo].[wikipedia_articles_embeddings]([content_vector]) 
with (metric = 'cosine', type = 'diskann'); 
go

-- Create vector index of half-precision vectors
-- Should take ~22 seconds on a 16 vCore server
create vector index vec_idx16 on [dbo].[wikipedia_articles_embeddings]([content_vector_fp16]) 
with (metric = 'cosine', type = 'diskann'); 
go

select * from sys.vector_indexes
go

set statistics time on
set statistics io on
go

/*
	RUN KNN (Exact) VECTOR SEARCH
*/
declare @qv vector(1536, float16) = (select top(1) v16 from #t where id=2);
select top (50) id, vector_distance('cosine', @qv, [content_vector_fp16]) as distance, title
from [dbo].[wikipedia_articles_embeddings]
order by distance;
go

/*
	RUN ANN (Approximate) VECTOR SEARCH
*/
declare @qv vector(1536, float16) = (select top(1) v16 from #t where id = 2);
select 
	t.id, s.distance, t.title
from
	vector_search(
		table = [dbo].[wikipedia_articles_embeddings] as t, 
		column = [content_vector_fp16], 
		similar_to = @qv, 
		metric = 'cosine', 
		top_n = 50
	) as s
order by s.distance, title
;
go

/*
	Calculate Recall and compare fp16 vs fp32
*/
declare @n int = 100;
declare @qv32 vector(1536, float32), @qv16 vector(1536, float16);
select top(1) @qv32 = v32, @qv16 = v16 from #t where id = 1;
with cteANN32 as
(
	select top (@n)
		t.id, s.distance, t.title
	from
		vector_search(
			table = [dbo].[wikipedia_articles_embeddings] as t, 
			column = [content_vector], 
			similar_to = @qv32, 
			metric = 'cosine', 
			top_n = @n
		) as s
	order by s.distance, id
),
cteANN16 as
(
	select top (@n)
		t.id, s.distance, t.title
	from
		vector_search(
			table = [dbo].[wikipedia_articles_embeddings] as t, 
			column = [content_vector_fp16], 
			similar_to = @qv16, 
			metric = 'cosine', 
			top_n = @n
		) as s
	order by s.distance, id
),
cteKNN32 as
(
	select top (@n) id, vector_distance('cosine', @qv32, [content_vector]) as distance, title
	from [dbo].[wikipedia_articles_embeddings]
	order by distance, id	
)
select
	k32.id as id_knn,
	a32.id as id_ann_fp32,
	a16.id as id_ann_fp16,
	k32.distance as distance_knn,
	a32.distance as distance_ann_fp32,
	a16.distance as distance_ann_fp16,
	running_recall_fp32 = cast(cast(count(a32.id) over (order by k32.distance) as float) 
				/ cast(count(k32.id) over (order by k32.distance) as float) as decimal(6,3)),
	running_recall_fp16 = cast(cast(count(a16.id) over (order by k32.distance) as float) 
				/ cast(count(k32.id) over (order by k32.distance) as float) as decimal(6,3))
from
	cteKNN32 k32
left outer join
	cteANN32 a32 on k32.id = a32.id
left outer join
	cteANN16 a16 on k32.id = a16.id
order by
	k32.distance
go
	
