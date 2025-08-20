/*
	This script requires SQL Server 2025 RC0
*/

use WikipediaTest
go

set statistics time off
go

select db_id(), @@spid
go

-- Enable trace flags for vector features
alter database scoped configuration
set preview_features = on;
go
select * from sys.database_scoped_configurations where [name] = 'preview_features'
go

--- Create Indexes 
--- (with 16 vCores, creation time is expected to be 40 seconds for each index)
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
	Option 1: LOAD A PRE-GENERATED EMBEDDING
	
	The following code loads a pre-generated embedding for the text
	"The foundation series by Isaac Asimov" using the "ada2-text-embedding" model
	Uncomment the following text if you don't have access to a OpenAI model,
	otherwise it is recommended to use the new "ai_generate_embedding" function
	by using the code in the "Option 2" section below
*/
/*
declare @j json = (select BulkColumn from 
			openrowset(bulk 'C:\samples\rc0\datasets\reference-embedding.json', single_clob) as j)
declare @qv vector(1536) = json_query(@j, '$."embedding-vector"')
drop table if exists #t;
create table #t (v vector(1536))
insert into #t values (@qv)
go
*/

/*
	Option 2: GENERATE EMBEDDING USING OPEN AI 

	The following code uses the new get_embeddings function to generate
	embeddings for the requested text. Make sure to have an OpenAI "ada2-text-embedding" 
	model deployed in OpenAI o Azure OpenAI. 
*/

-- Create database credentials to store API key
if not exists(select * from sys.symmetric_keys where [name] = '##MS_DatabaseMasterKey##')
begin
	create master key encryption by password = 'Pa$$_w0rd!ThatIS_L0Ng'
end
go
if exists(select * from sys.[database_scoped_credentials] where name = 'https://xyz.openai.azure.com/') -- use your Azure OpenAI endpoint
begin
	drop database scoped credential [https://xyz.openai.azure.com/];
end
create database scoped credential [https://xyz.openai.azure.com/]
with identity = 'HTTPEndpointHeaders', secret = '{"api-key": ""}'; -- Add your Azure OpenAI Key
go
select * from sys.[database_scoped_credentials]
go

-- Enable external rest endpoint used by get_embeddings procedure
exec sp_configure 'external rest endpoint enabled', 1
reconfigure
go

-- Create reference to OpenAI model
--drop external model Ada2Embeddings
--go
create external model Ada2Embeddings
with ( 
      location = 'https://xyz.openai.azure.com/openai/deployments/<deployment-name>/embeddings?api-version=2024-08-01-preview',
      credential = [https://xyz.openai.azure.com/],
      api_format = 'Azure OpenAI',
      model_type = embeddings,
      model = 'embeddings'
);
go
select * from sys.external_models
go

-- Generate embeddings and save it for future use
declare @qv vector(1536)
drop table if exists #t;
create table #t (v vector(1536))
insert into #t 
select ai_generate_embeddings(N'The foundation series by Isaac Asimov' use model Ada2Embeddings);
select * from  #t
go

/*
	RUN ANN (Approximate) VECTOR SEARCH
*/
declare @qv vector(1536) = (select top(1) v from #t);
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
order by s.distance, title
;
go

/*
	RUN KNN (Exact) VECTOR SEARCH
*/
declare @qv vector(1536) = (select top(1) v from #t);
select top (50) id, vector_distance('cosine', @qv, [content_vector]) as distance, title
from [dbo].[wikipedia_articles_embeddings]
order by distance
;
go

/*
	Calculate Recall
*/
declare @n int = 50;
declare @qv vector(1536) = (select top(1) v from #t);
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