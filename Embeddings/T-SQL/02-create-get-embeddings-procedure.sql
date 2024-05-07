/*
    Create a procedure to get the embeddings for the input text by calling the OpenAI API

    Replace <your-api-name> with the name of your Azure OpenAI service
*/
create or alter procedure dbo.get_embedding
@deployedModelName nvarchar(1000),
@inputText nvarchar(max),
@embedding varbinary(8000) output
as
declare @retval int, @response nvarchar(max);
declare @payload nvarchar(max) = json_object('input': @inputText);
declare @url nvarchar(1000) = 'https://<your-api-name>.openai.azure.com/openai/deployments/' + @deployedModelName + '/embeddings?api-version=2023-03-15-preview'
exec @retval = sp_invoke_external_rest_endpoint
    @url = @url,
    @method = 'POST',
    @credential = [https://<your-api-name>.openai.azure.com],
    @payload = @payload,
    @response = @response output;

declare @re varbinary(8000);
if (@retval = 0) begin
    set @re = json_array_to_vector(json_query(@response, '$.result.data[0].embedding'))
end else begin
    declare @msg nvarchar(max) =  
        'Error calling OpenAI API' + char(13) + char(10) + 
        '[HTTP Status: ' + json_value(@response, '$.response.status.http.code') + '] ' +
        json_value(@response, '$.result.error.message');
    throw 50000, @msg, 1;
end

set @embedding = @re;

return @retval
go

