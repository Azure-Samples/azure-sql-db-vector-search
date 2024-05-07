/*
    Create database credentials to store API key

    Replace <your-api-name> with the name of your Azure OpenAI service and <api-key> with the API key for the Azure OpenAI API
*/
if exists(select * from sys.[database_scoped_credentials] where name = 'https://<your-api-name>.openai.azure.com')
begin
	drop database scoped credential [https://<your-api-name>.openai.azure.com];
end
create database scoped credential [https://<your-api-name>.openai.azure.com]
with identity = 'HTTPEndpointHeaders', secret = '{"api-key": "<api-key>"}';
go