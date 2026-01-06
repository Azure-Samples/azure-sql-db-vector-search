/*
	Option 1: LOAD A PRE-GENERATED EMBEDDING (only for SQL Server 2025)
	
	The following code loads a pre-generated embedding for the text
	"The foundation series by Isaac Asimov" using the "ada2-text-embedding" model
	Uncomment the following text if you don't have access to a OpenAI model,
	otherwise it is recommended to use the new "ai_generate_embedding" function
	by using the code in the "Option 2" section below
*/
use WikipediaTest
go

drop table if exists dbo.wikipedia_search_vectors
go

declare @j json = (select BulkColumn from 
			openrowset(bulk 'C:\samples\rc1\datasets\reference-embedding.json', single_clob) as j)
declare @qv vector(1536) = json_query(@j, '$."embedding-vector"')
drop table if exists #t;
create table #t (v vector(1536));
insert into #t values (@qv);
select * from #t;
go
