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

-- Enable external rest endpoint used by sp_invoke_external_rest_endpoint procedure
exec sp_configure 'external rest endpoint enabled', 1
reconfigure
go

drop table if exists dbo.wikipedia_search_vectors
go

-- Download pre-generated search vector from GitHub
declare @response nvarchar(max)
exec sp_invoke_external_rest_endpoint 
	@url = 'https://raw.githubusercontent.com/Azure-Samples/azure-sql-db-vector-search/refs/heads/main/DiskANN/Wikipedia/reference-embedding.json',
	@method = 'GET',
	@response = @response output

declare @qv vector(1536) = json_query(@response, '$.result."embedding-vector"')
drop table if exists #t;
create table #t (v vector(1536));
insert into #t values (@qv);
select * from #t;

