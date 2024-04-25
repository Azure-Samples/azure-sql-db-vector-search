
/*Lets take a look at the data in the table. The dataset has been created using the customer reviews from FineFoods Amazon and enriching it with embeddings generated via the text-embedding-small OpenAI model.
The embeddings have been generated using the concatenation of Summary + Text
*/

select top(10) * from dbo.finefoodreviews 
order by ID

--To have the broadest compatibility with any language and platform in the first wave vectors will take advantage of existing VARBINARY data type to store vector binary format
--Add the New Column: vector with the type varbinary(8000)

ALTER TABLE [dbo].[finefoodreviews]
ADD [vectorbinary] varbinary(8000);

--Then, update the new column with the transformed data from the embedding column.
--We will pass the embeddings to the new built in function JSON_ARRAY_TO_VECTOR that will converts a JSON array to a compact binary representation of a vector

UPDATE [dbo].[finefoodreviews]
SET [vectorbinary] = JSON_ARRAY_TO_VECTOR([vector]);
GO

-- We can drop the previous vector column now as we will be using compact binary representation of a vector in the column vectorbinary created before this.

ALTER TABLE dbo.finefoodreviews
DROP COLUMN vector;

-- Vectors are stored in an efficient binary format that also enables usage of dedicated CPU vector processing extensions like SIMD and AVX.      

select top(5)  ID, ProductId text, summary , vectorbinary  from [dbo].[finefoodreviews]

/*

On that table we can create a column store index to efficiently store and search for vectors. Then it is just a matter of calculating the distance between vectors to find the closest. 
Thanks to the internal optimization of the columnstore (that uses SIMD AVX-512 instructions to speed up vector operations) the distance calculation to find the exact nearest neighbour search is extremely fast

*/

create clustered columnstore index Csindex on [dbo].[finefoodreviews]
order (ID, vectorbinary)
go



/*Specialized functions will allow developers to transform stored vector data back into JSON arrays and to check and mandate vector dimensionality. 
Lets take a look at how the vector is stored in the SQL DB table & also make use of the newly introduced helper function

ISVECTOR Checks if the provided object is a valid vector: Returns 1 if valid, otherwise returns 0. Returns NULL if the expression is NULL
VECTOR_DIMENSIONS Takes a vector as an input and returns the number of dimensions as an output. In this case we see the number of dimensions of the vector are 1536 (as we are using Azure OpenAI text embeddings)
VECTOR_TO_JSON_ARRAY Converts a vector in a compact binary format to a human-readable string format. The string format is the same as the one used by JSON to represent arrays
*/
SELECT TOP(5) ISVECTOR(vectorbinary) as isvector, VECTOR_DIMENSIONS(vectorbinary) as dimensions , summary , vectorbinary , VECTOR_TO_JSON_ARRAY(vectorbinary) as jsonvector,  ProductId FROM [dbo].[finefoodreviews]



/* Performing a similarity search

Lets now query our embedding table to get the top similar reviews given the User search query.
What we are doing: Given any user search query, we can get the vector representation of that text. Then we can use that vector to calculate the cosine distance against all the customer review comments stored in the database and take only the closest ones which will return the product most likely connect to the product we are interested in. The reviews with the highest similarity are considered the most relevant to the query, helping users discover products or experiences related to their search.
The most common distance is the cosine similarity, which can be calculated quite easily in SQL with the help of the new distance functions
This approach showcases the power of semantic search by finding reviews that are contextually related to the search query, even if they don’t contain exact match keywords  */



declare @e varbinary(8000) 
exec dbo.get_embeddings @model = 'pookamembedding', @text = 'help me find healthy cat food', @embedding = @e output;



SELECT TOP(10) ProductId, Summary, text,
           1 -vector_distance('cosine', @e, vectorbinary) AS similarity_score
    FROM dbo.finefoodreviews
    ORDER BY similarity_score desc
-- Assuming you have a stored procedure to get embeddings for a given text
declare @e varbinary(8000) 
exec dbo.get_embeddings @model = 'pookamembedding', @text = 'pet food', @embedding = @e output;



-- Hybrid query to find similar reviews based on vector similarity with simple filters

select top(10)
    f.Id,
    f.ProductId,
    f.UserId,
    f.Score,
    f.Summary,
    f.Text,
    f.combined,
    1-vector_distance('cosine', f.vectorbinary, @e) as similarity
from
    finefoodreviews f
where
    f.Score <= 2 -- Assuming you want to filter by low scores
order by
    vector_distance('cosine', f.vectorbinary, @e)





-- Comprehensive query with multiple filters.
--This approach showcases the power of semantic search by finding reviews that are contextually related to the search query, even if they don’t contain exact match keywords. It also demonstrates how keyword search can be used in conjunction to ensure that certain words are present in the results
declare @e varbinary(8000) 
exec dbo.get_embeddings @model = 'pookamembedding', @text = 'help me find negative reviews for hot beverages', @embedding = @e output;


select top(50)

    f.Id,
    f.ProductId,
    f.UserId,
    f.Score,
    f.Summary,
    f.Text,
    f.combined,
    1-vector_distance('cosine', f.vectorbinary, @e) as similarity,

    case 
        when len(f.Text) > 100 then 'Detailed Review'
        else 'Short Review'
    end as ReviewLength,

    case 
        when f.Score >= 4 then 'High Score'
        when f.Score between 2 and 3 then 'Medium Score'
        else 'Low Score'
    end as ScoreCategory
from
    finefoodreviews f
where
    --f.ProductId = 'B003VXFK44' -- Product-based filter
    -- and f.UserId not like 'Anonymous%' -- User-based filter to exclude anonymous users
    --and DATEDIFF(second, '1970-01-01', getdate()) - f.Time <= 31536000 -- Time-based filter for reviews in the last year
     f.Score <= 2 -- Score threshold filter
    --and len(f.Text) > 50 -- Text length filter for detailed reviews
    --and (charindex('horrible', f.Text) > 0 or charindex('worst', f.Text) > 0) -- Keyword presence filter
    and f.Text like '%disappointing%' or f.Text like '%worst%' -- Inclusion of specific negative words
order by
    similarity desc, -- Order by similarity score
    f.Score desc, -- Secondary order by review score
    ReviewLength desc -- Tertiary order by review length



