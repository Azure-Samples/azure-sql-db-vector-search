# About this Repo

<span style="color: rgb(31, 35, 40); font-family: -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, &quot;Noto Sans&quot;, Helvetica, Arial, sans-serif, &quot;Apple Color Emoji&quot;, &quot;Segoe UI Emoji&quot;; font-size: 16px; background-color: rgb(255, 255, 255);">This repo hosts samples meant to help use the new&nbsp;<b>Native Vector Support in SQL DB</b> feature</span><span style="color: rgb(31, 35, 40); font-family: -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, &quot;Noto Sans&quot;, Helvetica, Arial, sans-serif, &quot;Apple Color Emoji&quot;, &quot;Segoe UI Emoji&quot;; font-size: 16px; background-color: rgb(255, 255, 255);">. We illustrate key technical concepts and demonstrate how you can store and query embeddings in Azure SQL data to enhance your application with AI capabilities.</span>

# Native Vector Support in Azure SQL and SQL Server

The first wave of vector support will introduce **specialized vector functions to create vectors from JSON array,** as they are the most common way to represent a vector, to calculate **Euclidean, Cosine** distances as well as calculating the **Dot Product** between two vectors. 

Vectors are stored in an **efficient binary format** that also enables usage of dedicated CPU vector processing extensions like SIMD and AVX. 

To have the broadest compatibility with any language and platform in the first wave vectors will take advantage of **existing VARBINARY data type** to store vector binary format. Specialized functions will allow developers to transform stored vector data back into JSON arrays and to check and mandate vector dimensionality. 

Embeddings can be efficiently stored and queried using to columnstore index support, allowing **exact nearest neighbour** search with great performance.

## Features

The following scalar functions are introduced to perform operations on vectors in binary format, allowing applications to store and manipulate vectors in SQL Server.

|  |  |
| --- | --- |
| **Function** | **Description** |
| <span style="color:#002060">JSON_ARRAY_TO_VECTOR (Transact-SQL)</span> | Creates a vector from a JSON array |
| <span style="color:#002060">ISVECTOR (Transact-SQL)</span> | Tests whether a binary contains a valid vector |
| <span style="color:#002060">VECTOR_TO_JSON_ARRAY (Transact-SQL)</span> | Returns a vector as a JSON array |
| <span style="color:#002060">VECTOR_DISTANCE (Transact-SQL)</span> | Calculates the distance between two vectors using a specified distance metric |
| <span style="color:#002060">VECTOR_DIMENSIONS(Transact-SQL)</span> | Takes a vector as an input and returns the number of dimensions as an output |

**Note**: These functions are in preview and is subject to change. Preview features are not meant for production use and are subject to additional terms of use.

### NDA

The contents of this document are confidential and participation in the preview program is covered by your NDA (Non-Disclosure Agreement) with Microsoft. The details within this document are not to be shared without receiving prior approval from the Microsoft Azure SQL Database team. Please reach out to your PM Buddy if you have further questions. Your PM Buddy will make sure that you are covered by an NDA before the engagement begins.

### Disclaimer

We recommend that you first try out in a dev-test environment.The preview bits are not to be used for Production environments. In the initial preview stages, it is possible that some database operations might not perform most optimally. We strive hard to reduce the probability of disasters by rigorously testing in-house however these incidents can occur during the preview stages. For test workloads and PoC we advise that you plan for interruptions. We recommend that you also perhaps consider modularizing your testing components so that in case of a disaster they can be re-configured and deployed easily to resume the testing process. 

## Getting Started
See the description in each sample for instructions (projects will have either a README file or instructions in the notebooks themselves.)


#### Prerequisites
1.       An Azure subscription - [<span style="color:#002060">Create one for free</span>](https://github.com/Azure-Samples/azure-sql-db-vector-search/blob/622f7be47cafa261b267163a9a94af13d4fa9243/AzureSQLVectorSearch/src/https:/azure.microsoft.com/free/cognitive-services?azure-portal=true)

2.       Azure SQL Database - [<span style="color:#002060">Create one for free</span>](https://github.com/Azure-Samples/azure-sql-db-vector-search/blob/622f7be47cafa261b267163a9a94af13d4fa9243/AzureSQLVectorSearch/src/https:/learn.microsoft.com/azure/azure-sql/database/free-offer?view=azuresql)

3.       Make sure you have an [<span style="color:#002060">Azure OpenAI</span>](https://learn.microsoft.com/en-us/azure/ai-services/openai/overview) resource created in your Azure subscription.


# Available Samples  

## [Create, store and query OpenAI embeddings in Azure SQL DB](https://github.com/Azure-Samples/azure-sql-db-vector-search/tree/01cfeb41dad05d5667f2c9d1f14956bd045ec953/VectorSearch_Notebooks/Python_Notebook_Example)  

This Python notebook is a step by step guide that will show you:

- How to create embeddings from content using the Azure OpenAI API
- How to use Azure SQL DB as a vector database and store embeddings data in SQL & perform similarity search directly from within SQL itself
- How to use embeddings retrieved from a vector database to augment LLM generation for a Chatbot.  You'll be able to ask queries in natural language and get answers from the OpenAI GPT model, using the data you have in Azure SQL Database.

<span style="color: rgb(31, 35, 40); font-family: -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, &quot;Noto Sans&quot;, Helvetica, Arial, sans-serif, &quot;Apple Color Emoji&quot;, &quot;Segoe UI Emoji&quot;; font-size: 16px; background-color: rgb(255, 255, 255);">We will be using the Fine Foods Review Dataset available on Kaggle. This dataset consists of customer reviews of fine foods from Amazon&nbsp;<br></span>  <span style="font-size: 16px;"><br><br></span>


## [Store and query OpenAI embeddings in Azure SQL DB (TSQL)](https://github.com/Azure-Samples/azure-sql-db-vector-search/tree/01cfeb41dad05d5667f2c9d1f14956bd045ec953/VectorSearch_Notebooks/SQL_Notebook_Example)  

We will be using a [SQL notebook](https:\github.com\Azure-Samples\azure-sql-db-vector-search\blob\d1a3b8e723cf3f80d932588604c92f9da5ef9e65\VectorSearch_Notebooks\SQL_Notebook_Example\SQLvectorsearchnotebook.ipynb) to demonstrate how to perform Vector Similarity Search in SQL DB. It showcases the power of semantic search by finding reviews that are contextually related to the search query, even if they don’t contain exact match keywords. It also demonstrates how keyword search can be used in conjunction to ensure that certain words are present in the results


## [Hybrid Search](https://github.com/Azure-Samples/azure-sql-db-vector-search/tree/01cfeb41dad05d5667f2c9d1f14956bd045ec953/GenerateEmbeddings/Python)  

This sample shows how to combine Fulltext search in Azure SQL database with BM25 ranking and cosine similarity ranking to do hybrid search.

In this sample the local model [multi-qa-MiniLM-L6-cos-v1](https:\huggingface.co\sentence-transformers\multi-qa-MiniLM-L6-cos-v1) to generate embeddings. The Python script `./python/hybrid_search.py` shows how to

- use Python to generate the embeddings
- do similarity search in Azure SQL database
- use [Fulltext search in Azure SQL database with BM25 ranking](https:\learn.microsoft.com\en-us\sql\relational-databases\search\limit-search-results-with-rank?view=sql-server-ver16#ranking-of-freetexttable)
- do re-ranking applying Reciprocal Rank Fusion (RRF) to combine the BM25 ranking with the cosine similarity ranking


## [Get Embeddings from OpenAI from Azure SQL](https://github.com/Azure-Samples/azure-sql-db-vector-search/tree/01cfeb41dad05d5667f2c9d1f14956bd045ec953/GenerateEmbeddings/T-SQL)  

In this sample you'll be creating a stored procedure to easily transform text into a vector using OpenAI embedding model.


## Resources

- [Create and deploy an Azure OpenAI Service resource](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/create-resource?pivots=web-portal)
- [Embeddings models](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models#embeddings-models)
- [SQL AI Samples and Examples](https://aka.ms/sqlaisamples)
- [Frequently asked questions about Copilot in Azure SQL Database (preview)](https://learn.microsoft.com/en-us/azure/azure-sql/copilot/copilot-azure-sql-faq?view=azuresql)
- [Responsible AI FAQ for Microsoft Copilot for Azure (preview)](https://learn.microsoft.com/en-us/azure/copilot/responsible-ai-faq)

**Trademarks**

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft trademarks or logos is subject to and must follow [Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general). Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship. Any use of third-party trademarks or logos are subject to those third-party's policies.
