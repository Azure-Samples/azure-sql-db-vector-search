/* OpenAI models are available as REST endpoints and thus can be easily consumed from Azure SQL Database using the sp_invoke_external_rest_endpoint system stored procedure:
Using a call to a REST service to get embeddings is just one of the integration options you have when working with SQL Database and OpenAI. 
You can let any of the available models access data stored in Azure SQL Database to create solutions where your users can interact with the data as shown here 
*/

CREATE PROCEDURE [dbo].[get_embeddings]
(
    @model VARCHAR(MAX),
    @text NVARCHAR(MAX),
    @embedding VARBINARY(8000) OUTPUT
)
AS
BEGIN
    DECLARE @retval INT, @response NVARCHAR(MAX);
    DECLARE @url VARCHAR(MAX);
    DECLARE @payload NVARCHAR(MAX) = json_object('input': @text);

    -- Set the @url variable with proper concatenation before the exec statement
    SET @url = 'https://<yourdeploymentname>.openai.azure.com/openai/deployments/' + @model + '/embeddings?api-version=2023-03-15-preview';

    EXEC dbo.sp_invoke_external_rest_endpoint 
        @url = @url,
        @method = 'POST',   
        @payload = @payload,   
        @headers = '{"Content-Type":"application/json", "api-key":"<APIKEY>"}', 
        @response = @response OUTPUT;

    DECLARE @jsonArray NVARCHAR(MAX) = '';
    DECLARE @first BIT = 1;

    -- Use a cursor to iterate through the JSON elements and build the array
    DECLARE @value NVARCHAR(MAX);
    DECLARE json_cursor CURSOR FOR
    SELECT [value]
    FROM OPENJSON(@response, '$.result.data[0].embedding');

    OPEN json_cursor;
    FETCH NEXT FROM json_cursor INTO @value;

    WHILE @@FETCH_STATUS = 0
    BEGIN
        IF @first = 1
            SET @first = 0;
        ELSE
            SET @jsonArray = @jsonArray + ',';

        SET @jsonArray = @jsonArray + CAST(@value AS NVARCHAR(MAX));
        FETCH NEXT FROM json_cursor INTO @value;
    END;

    CLOSE json_cursor;
    DEALLOCATE json_cursor;

    -- Enclose the values in brackets to form a valid JSON array
    SET @jsonArray = '[' + @jsonArray + ']';

    -- Convert the JSON array to a vector
    SET @embedding = json_array_to_vector(@jsonArray);
END
GO
