# Hybrid Search 

This sample shows how to combine Fulltext search in Azure SQL database with BM25 ranking and cosine similarity ranking to do hybrid search.

In this sample the local model [multi-qa-MiniLM-L6-cos-v1](https://huggingface.co/sentence-transformers/multi-qa-MiniLM-L6-cos-v1) to generate embeddings. The Python script `./python/hybrid_search.py` shows how to 

- use Python to generate the embeddings 
- do similarity search in Azure SQL database
- use [Fulltext search in Azure SQL database with BM25 ranking](https://learn.microsoft.com/en-us/sql/relational-databases/search/limit-search-results-with-rank?view=sql-server-ver16#ranking-of-freetexttable)
- do re-ranking applying Reciprocal Rank Fusion (RRF) to combine the BM25 ranking with the cosine similarity ranking

Make sure to setup the database for this sample using the `./python/00-setup-database.sql` script. Database can be either an Azure SQL DB or a SQL Server database. Once the database has been created, you can run the `./python/hybrid_search.py` script to do the hybrid search:

First, set up the virtual environment and install the required packages:

```bash
python -m venv .venv
```

Activate the virtual environment and then install the required packages:

```bash
pip install -r requirements.txt
```

Create an environment file `.env` with the connection string to Azure SQL database. You can use the `.env.sample` as a starting point. The sample `.env` file shows how to use Entra ID to connect to the database, which looks like:

```text
MSSQL='Driver={ODBC Driver 18 for SQL Server};Server=tcp:<server>,1433;Database=<database>;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;LongAsMax=yes;'
```

If you want to use SQL Authentication the connection string would instead look like the following:

```
MSSQL='Driver={ODBC Driver 18 for SQL Server};Server=tcp:<server>,1433;Database=<database>;UID=<user>;PWD=<password>;Encrypt=yes;TrustServerCertificate=yes;Connection Timeout=30;LongAsMax=yes;'
```

Then run the script:    

```bash
python hybrid_search.py
```