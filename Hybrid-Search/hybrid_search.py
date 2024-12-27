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
        'The bear is growling'
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
                INSERT INTO dbo.documents (id, content, embedding)
                VALUES (?, ?, CAST(CAST(? as NVARCHAR(MAX)) AS VECTOR(384)));
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
    
    print('Querying database...')  
    k = 5  
    try:
        cursor = conn.cursor()  
        
        results  = cursor.execute(f"""
            DECLARE @k INT = ?;
            DECLARE @q NVARCHAR(1000) = ?;
            DECLARE @v VECTOR(384) = CAST(CAST(? as NVARCHAR(MAX)) AS VECTOR(384));
            WITH keyword_search AS (
                SELECT TOP(@k)
                    id, 
                    RANK() OVER (ORDER BY rank) AS rank
                FROM
                    (
                        SELECT TOP(@k)
                            id,
                            ftt.[RANK] AS rank
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
            )
            SELECT TOP(@k)
                COALESCE(ss.id, ks.id) AS id,
                COALESCE(1.0 / (@k + ss.rank), 0.0) +
                COALESCE(1.0 / (@k + ks.rank), 0.0) AS score -- Reciprocal Rank Fusion (RRF) 
            FROM
                semantic_search ss
            FULL OUTER JOIN
                keyword_search ks ON ss.id = ks.id
            ORDER BY 
                score DESC
            """,
            k,
            query, 
            json.dumps(embedding.tolist()),        
        )

        for row in results:
            print(f'Document: {row[0]} -> RRF score: {row[1]:0.4}')

    finally:
        cursor.close()
