/*
	This script requires SQL Server 2025
*/

use WikipediaTest
go

set statistics time off
go

select db_id()
go

-- Enable trace flags for vector features
dbcc traceon (466, 474, 13981, -1) 
go

-- Check trace flags status
dbcc tracestatus
go

--- Create Indexes 
--- (with 16 vCores, creation time is expected to be ~1:00 minutes for each index)
--- Monitor index creation progress using:
--- select session_id, status, command, percent_complete from sys.dm_exec_requests where session_id = <session id>

create vector index vec_idx on [dbo].[wikipedia_articles_embeddings]([title_vector_ada2]) 
with (metric = 'cosine', type = 'diskann', maxdop=8); 
go

create vector index vec_idx2 on [dbo].[wikipedia_articles_embeddings]([content_vector_ada2]) 
with (metric = 'cosine', type = 'diskann'); 
go

select * from sys.indexes where type = 8
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
			openrowset(bulk 'C:\sql-server-2025\samples\azure-sql-db-vector-search\DiskANN\Wikipedia\reference-embedding.json', single_clob) as j)
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

-- Generate embeddings and save it for future use
declare @qv vector(1536)
drop table if exists #t;
create table #t (v vector(1536))
insert into #t 
select ai_generate_embeddings(N'The foundation series by Isaac Asimov' model Ada2Embeddings);
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
		column = [content_vector_ada2], 
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
select top (50) id, vector_distance('cosine', @qv, [content_vector_ada2]) as distance, title
from [dbo].[wikipedia_articles_embeddings]
order by distance
;
go
