# Native Vector Support in Azure SQL and SQL Server

This repo hosts samples meant to help use the new [**Native Vector Support in Azure SQL DB**](https://devblogs.microsoft.com/azure-sql/announcing-general-availability-of-native-vector-type-functions-in-azure-sql/) feature. We illustrate key technical concepts and demonstrate how you can store and query embeddings in Azure SQL data to enhance your application with AI capabilities.

## Prerequisites

To use the provided samples make sure you have the following pre-requisites:

1. An Azure subscription - [Create one for free](https://azure.microsoft.com/pricing/purchase-options/azure-account)

1. Azure SQL Database - [Create one for free](https:/learn.microsoft.com/azure/azure-sql/database/free-offer?view=azuresql) or [SQL Server 2025](https://www.microsoft.com/en-us/evalcenter/sql-server-2025-downloads) if you want to test DiskANN.

1. Make sure you have an [Azure OpenAI](https://learn.microsoft.com/azure/ai-services/openai/overview) resource created in your Azure subscription.

1. Visual Studio Code with MSSQL Extension
   - Download it for [Free](https://code.visualstudio.com/) and then install the [MSSQL](https://marketplace.visualstudio.com/items?itemName=ms-mssql.mssql) extension, or
   - [SQL Server Management Studio](https://learn.microsoft.com/sql/ssms/download-sql-server-management-studio-ssms).

1. If you are going to clone this repository in your machine, make sure to have installed the `git-lfs` extension: [Git Large File Storage](https://git-lfs.com/)

1. For testing DiskANN you need to use SQL Server 2025 or Azure SQL. See the announcement here:
  
    - [SQL Server 2025 Embraces Vectors: setting the foundation for empowering your data with AI](https://devblogs.microsoft.com/azure-sql/sql-server-2025-embraces-vectors-setting-the-foundation-for-empowering-your-data-with-ai/)
  
    - [Public preview of vector indexing in Azure SQL DB, Azure SQL MI, and SQL database in Microsoft Fabric](https://devblogs.microsoft.com/azure-sql/public-preview-of-vector-indexing-in-azure-sql-db-azure-sql-mi-and-sql-database-in-microsoft-fabric/)


## Samples  

### Getting Started

A simple getting started to get familiar with common vector functions is available here: [Getting-Started](./Getting-Started/getting-started.ipynb)

### Embeddings

Learn how to get embeddings from OpenAI directly from Azure SQL using the sample available the [Embeddings/T-SQL](./Embeddings/T-SQL) folder.

### Exact Vector Search

The [Vector-Search](./Vector-Search) example illustrates the implementation of Vector Similarity Search within an SQL database, highlighting the capabilities of semantic search. By leveraging vector representations of text, the system can identify reviews that share contextual similarities with a given search query, transcending the limitations of keyword exact matches. Additionally, it demonstrates the integration of Keyword Search to guarantee the inclusion of specific terms within the search outcomes.

### Approximate Vector Search

The [DiskANN](./DiskANN/) folder contains a sample that demonstrates how to use the new `VECTOR_SEARCH` function with DiskANN. The sample uses a subset of Wikipedia data to create a table with a vector column, insert data, and perform approximate nearest neighbor search using the `VECTOR_SEARCH` function.

This sample, at the moment, requires SQL Server 2025 or Azure SQL. See the announcement here:

- [SQL Server 2025 Embraces Vectors: setting the foundation for empowering your data with AI](https://devblogs.microsoft.com/azure-sql/sql-server-2025-embraces-vectors-setting-the-foundation-for-empowering-your-data-with-ai/)
- [Public preview of vector indexing in Azure SQL DB, Azure SQL MI, and SQL database in Microsoft Fabric](https://devblogs.microsoft.com/azure-sql/public-preview-of-vector-indexing-in-azure-sql-db-azure-sql-mi-and-sql-database-in-microsoft-fabric/)

### Hybrid Search

The Python sample in the [Hybrid-Search](./Hybrid-Search/) folder shows how to combine Fulltext search in Azure SQL database with BM25 ranking and cosine similarity ranking to do hybrid search.

### Semantic Reranking Vector Search

Rerank models evaluate and reorder text inputs according to their semantic relevance to a specific query, and are often applied after an initial search to improve result quality. A sample using a semantic re-ranker to improve the output of vector search can be found here: [Semantic-Reranking](./Semantic-Reranking).

### Retrieval Augmented Generation

The RAG pattern is a powerful way to generate text using a pre-trained language model and a retrieval mechanism. The [Retrieval Augmented Generation](./Retrieval-Augmented-Generation) folder contains a sample that demonstrates how to use the RAG pattern with Azure SQL and Azure OpenAI, using Python notebooks.

#### DiskANN and Hybrid Search

Using DiskANN together with FullText enables you to do hybrid search. The [DiskANN](./DiskANN/) folder contains the file `004-wikipedia-hybrid-search.sql` that demonstrates how to use the the new `VECTOR_SEARCH` function along with `FREETEXTTABLE` to implement hybrid search with Reciprocal Rank Fusion (RRF) and BM25 ranking.

### SQL Client

If you are using SQL Client directly in your applications, you can use the [SqlClient](./DotNet) folder to see how to use Native Vector Search in C#/.NET.

### Entity Framework Core

If you are using .NET EF Core, you can use the [EF-Core](./DotNet) sample to see how to use the new vector functions in your application.

### Dapper

If you are using the MicroORM Dapper, you can use the [Dapper](./DotNet) sample to see how to use the new vector functions in your application.

### Semantic Kernel

[Semantic Kernel](https://github.com/microsoft/semantic-kernel) is an SDK that simplifies the creation of enterprise AI-enabled applications. Details on support for SQL Server and Azure SQL as vectors stores are available in the [SemanticKernel](./SemanticKernel) folder.

## Resources

- [Create and deploy an Azure OpenAI Service resource](https://learn.microsoft.com/azure/ai-services/openai/how-to/create-resource?pivots=web-portal)
- [Embeddings models](https://learn.microsoft.com/azure/ai-services/openai/concepts/models#embeddings-models)
- [SQL AI Samples and Examples](https://aka.ms/sqlaisamples)
- [Frequently asked questions about Copilot in Azure SQL Database (preview)](https://learn.microsoft.com/azure/azure-sql/copilot/copilot-azure-sql-faq?view=azuresql)
- [Responsible AI FAQ for Microsoft Copilot for Azure (preview)](https://learn.microsoft.com/azure/copilot/responsible-ai-faq)

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft trademarks or logos is subject to and must follow [Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualproperty/trademarks/usage/general). Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship. Any use of third-party trademarks or logos are subject to those third-party's policies.
