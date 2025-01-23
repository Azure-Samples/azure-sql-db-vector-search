import os
import pyodbc
import logging
import json
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from utilities import get_mssql_connection

load_dotenv()

if __name__ == '__main__':
    print('Initializing sample...')
    print('Getting embeddings...')    
    sentences = [
        'The dog is barking',
        'The cat is purring',
        'The bear is growling',
        'The bear roars'
    ]
    model = SentenceTransformer('multi-qa-MiniLM-L6-cos-v1') # returns a 384-dimensional vector
    embeddings = model.encode(sentences)

    conn = get_mssql_connection()

    print('Cleaning up the database...')
    try:
        cursor = conn.cursor()    
        cursor.execute("DELETE FROM dbo.documents;")
        cursor.commit();        
    finally:
        cursor.close()

    print('Saving documents and embeddings in the database...')    
    try:
        cursor = conn.cursor()  
        
        for id, (content, embedding) in enumerate(zip(sentences, embeddings)):
            cursor.execute(f"""
                INSERT INTO dbo.documents (id, content, embedding) VALUES (?, ?, CAST(? AS VECTOR(384)));
            """,
            id,
            content, 
            json.dumps(embedding.tolist())
            )

        cursor.commit()
    finally:
        cursor.close()

    print('Searching for similar documents...')
    print('Getting embeddings...')    
    query = 'growling bear'
    embedding = model.encode(query)    
    
    print(f'Querying database for "{query}"...') 
    k = 5  
    try:
        cursor = conn.cursor()  
        
        results  = cursor.execute(f"""
            DECLARE @k INT = ?;
            DECLARE @q NVARCHAR(1000) = ?;
            DECLARE @v VECTOR(384) = CAST(? AS VECTOR(384));
            WITH keyword_search AS (
                SELECT TOP(@k)
                    id, 
                    RANK() OVER (ORDER BY ft_rank DESC) AS rank
                FROM
                    (
                        SELECT TOP(@k)
                            id,
                            ftt.[RANK] AS ft_rank
                        FROM 
                            dbo.documents 
                        INNER JOIN 
                            FREETEXTTABLE(dbo.documents, *, @q) AS ftt ON dbo.documents.id = ftt.[KEY]
                    ) AS freetext_documents
            ),
            semantic_search AS
            (
                SELECT TOP(@k)
                    id, 
                    RANK() OVER (ORDER BY cosine_distance) AS rank
                FROM
                    (
                        SELECT 
                            id, 
                            VECTOR_DISTANCE('cosine', @v, embedding) AS cosine_distance
                        FROM 
                            dbo.documents
                    ) AS similar_documents
            ),
            result AS (
                SELECT TOP(@k)
                    COALESCE(ss.id, ks.id) AS id,
                    ss.rank AS semantic_rank,
                    ks.rank AS keyword_rank,
                    COALESCE(1.0 / (@k + ss.rank), 0.0) +
                    COALESCE(1.0 / (@k + ks.rank), 0.0) AS score -- Reciprocal Rank Fusion (RRF) 
                FROM
                    semantic_search ss
                FULL OUTER JOIN
                    keyword_search ks ON ss.id = ks.id
                ORDER BY 
                    score DESC
            )   
            SELECT
                d.id,
                semantic_rank,
                keyword_rank,
                score,
                content
            FROM
                result AS r
            INNER JOIN
                dbo.documents AS d ON r.id = d.id
            """,
            k,
            query, 
            json.dumps(embedding.tolist()),        
        )

        for row in results:
            print(f'Document: {row[0]} (content: {row[4]}) -> RRF score: {row[3]:0.4} (Semantic Rank: {row[1]}, Keyword Rank: {row[2]})')

    finally:
        cursor.close()
