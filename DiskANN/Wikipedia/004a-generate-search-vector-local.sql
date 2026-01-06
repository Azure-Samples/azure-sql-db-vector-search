/*
	Option 1: LOAD A PRE-GENERATED EMBEDDING (only for SQL Server 2025)
	
	The following code loads a pre-generated embedding for the text
	"The foundation series by Isaac Asimov" using the "ada2-text-embedding" model
	Uncomment the following text if you don't have access to a OpenAI model,
	otherwise it is recommended to use the new "ai_generate_embedding" function
	by using the code in the file '004c-generate-search-vector-openai.sql'
*/
use WikipediaTest
go

-- Save embeddings for future use
drop table if exists dbo.wikipedia_search_vectors;
create table dbo.wikipedia_search_vectors (id int primary key, q nvarchar(max), v vector(1536))
go

declare @j json = (select BulkColumn from 
			openrowset(bulk 'C:\Work\git\azure-sql-db-vector-search\DiskANN\Wikipedia\reference-embedding.json', single_clob) as j)

insert into dbo.wikipedia_search_vectors (id, q, v) 
select 1, * from openjson(@j) with 
(
	[q] nvarchar(max) '$."source-text"',
	[v] nvarchar(max) '$."embedding-vector"' as json
)
go

select * from dbo.wikipedia_search_vectors;
go


