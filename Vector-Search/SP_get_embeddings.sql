/* OpenAI models are available as REST endpoints and thus can be easily consumed from Azure SQL Database using the sp_invoke_external_rest_endpoint system stored procedure:
Using a call to a REST service to get embeddings is just one of the integration options you have when working with SQL Database and OpenAI. 
You can let any of the available models access data stored in Azure SQL Database to create solutions where your users can interact with the data as shown here 
*/

create procedure [dbo].[get_embeddings]
(
    @model varchar(max),
    @text nvarchar(max),
    @embedding varbinary(8000) output
)
as
begin
    declare @retval int, @response nvarchar(max);
    declare @url varchar(max);
    declare @payload nvarchar(max) = json_object('input': @text);

    -- Set the @url variable with proper concatenation before the exec statement
    set @url = 'https://<resourcename>.openai.azure.com/openai/deployments/' + @model + '/embeddings?api-version=2023-03-15-preview';

    exec dbo.sp_invoke_external_rest_endpoint 
        @url = @url,
        @method = 'POST',   
        @payload = @payload,   
        @headers = '{"Content-Type":"application/json", "api-key":"<openAIkey>"}', 
        @response = @response output;

    -- Use json_query to extract the embedding array directly
    declare @jsonArray nvarchar(max) = json_query(@response, '$.result.data[0].embedding');

    -- Assuming json_array_to_vector can handle the JSON array format
    set @embedding = json_array_to_vector(@jsonArray);
end
GO
