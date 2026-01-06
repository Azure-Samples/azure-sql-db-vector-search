/*
	Option 3: Generate embeddings using OpenAI

	The following code uses the new get_embeddings function to generate
	embeddings for the requested text. Make sure to have an OpenAI "ada2-text-embedding" 
	model deployed in OpenAI o Azure OpenAI. 
*/

-- Create database credentials to store OpenAI credentials
-- It is recommended to use Managed Identity, as explained here: 
-- https://devblogs.microsoft.com/azure-sql/go-passwordless-when-calling-azure-openai-from-azure-sql-using-managed-identities/
if not exists(select * from sys.database_scoped_credentials where [name] = 'https://<endpoint>.openai.azure.com')
begin
    create database scoped credential [https://<endpoint>.openai.azure.com]
    with identity = 'Managed Identity', secret = '{"resourceid":"https://cognitiveservices.azure.com"}';
	--or
	--with identity = 'HTTPEndpointHEader', secret = '{"api-key":"<api-key>"}';
end
go
select * from sys.database_scoped_credentials
go

-- Create external model
if not exists(select * from sys.external_models where [name] = 'Ada2Embeddings')
begin
	create external model Ada2Embeddings
	with ( 
		location = 'https://<endpoint>.openai.azure.com/openai/deployments/<deployment>/embeddings?api-version=2023-05-15',
		credential = [https://<endpoint>.openai.azure.com],
		api_format = 'Azure OpenAI',
		model_type = embeddings,
		model = 'embeddings'
	);
end
go
select * from sys.external_models
go

-- Generate embeddings and save it for future use
drop table if exists dbo.wikipedia_search_vectors;
create table dbo.wikipedia_search_vectors (id int primary key, q nvarchar(max), v vector(1536))
go

insert into 
	dbo.wikipedia_search_vectors (id, q) 
values
	(1, N'The foundation series by Isaac Asimov');
go
update dbo.wikipedia_search_vectors
set v = ai_generate_embeddings(q use model Ada2Embeddings)
where v is null
go

select * from dbo.wikipedia_search_vectors;
go

