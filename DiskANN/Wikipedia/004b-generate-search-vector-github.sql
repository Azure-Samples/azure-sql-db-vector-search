/*
	Option 2: Get the pre-calculated embedding via REST call (only for SQL Server 2025)

	The following code loads a pre-generated embedding for the text
	"The foundation series by Isaac Asimov" using the "ada2-text-embedding" model
	Uncomment the following text if you don't have access to a OpenAI model,
	otherwise it is recommended to use the new "ai_generate_embedding" function
	by using the code in the "Option 2" section below
*/
use WikipediaTest
go

-- Save embeddings for future use
drop table if exists dbo.wikipedia_search_vectors;
create table dbo.wikipedia_search_vectors (id int primary key, q nvarchar(max), v vector(1536))
go

-- Download pre-generated search vector from GitHub
declare @response nvarchar(max)
exec sp_invoke_external_rest_endpoint 
	@url = 'https://raw.githubusercontent.com/Azure-Samples/azure-sql-db-vector-search/refs/heads/main/DiskANN/Wikipedia/reference-embedding.json',
	@method = 'GET',
	@response = @response output

declare @j json = json_query(@response, '$.result')

insert into dbo.wikipedia_search_vectors (id, q, v) 
select 1, * from openjson(@j) with 
(
	[q] nvarchar(max) '$."source-text"',
	[v] nvarchar(max) '$."embedding-vector"' as json
)
go

select * from dbo.wikipedia_search_vectors;
go


