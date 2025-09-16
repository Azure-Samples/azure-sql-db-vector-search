# Approximate Nearest Neighbor Search

SQL Server 2025 introduces a new `VECTOR_SEARCH` function that allows you to perform approximate nearest neighbor search using the DiskANN algorithm. This function is designed to work with vector columns in SQL Server, enabling efficient similarity search on high-dimensional data.

The samples in this folder demonstrate how to use the `VECTOR_SEARCH` function with DiskANN. The samples include:

- Creating a table with a vector column, importing data from a CSV file, and inserting data into the table.
- Creating a approximate vector index on the table using `CREATE VECTOR INDEX` statement.
- Performing approximate nearest neighbor search using the `VECTOR_SEARCH` function.
- Performing hybrid search using the `VECTOR_SEARCH` function along with full-text search.
- Use Half-Precision floating points to store embeddings to have a more compact representation of vectors.
- Use the Vectorizer to generate embeddings for text data.

## Vectorizer

To quickly generate embeddings for existing text data, you can use the Vectorizer, which is available as an sample open-source project here: [azure-sql-db-vectorizer](https://github.com/Azure-Samples/azure-sql-db-vectorizer)

## End-To-End sample

A full end-to-end sample using Streamlit is available here: https://github.com/Azure-Samples/azure-sql-diskann
