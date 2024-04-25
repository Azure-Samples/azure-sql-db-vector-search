/*
    Get the embeddings for the input text by calling the OpenAI API
*/
declare @king varbinary(8000), @queen varbinary(8000), @pizza varbinary(8000);

exec dbo.get_embedding @deployedModelName = '<deployment-name>', @inputText = 'King', @embedding = @king output;
exec dbo.get_embedding @deployedModelName = '<deployment-name>', @inputText = 'Queen', @embedding = @queen output;
exec dbo.get_embedding @deployedModelName = '<deployment-name>', @inputText = 'Pizza', @embedding = @pizza output;

-- Find distance between vectorized cocepts. 
-- The smaller the distance, the more similar the concepts are.
select
    vector_distance('cosine', @king, @king) as 'King vs King',  
    vector_distance('cosine', @king, @queen) as 'King vs Queen',    
    vector_distance('cosine', @king, @pizza) as 'King vs Pizza'



