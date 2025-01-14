# Native Vector Support in Azure SQL and SQL Server

This repo hosts samples meant to help use the new **Native Vector Support in Azure SQL DB** feature. We illustrate key technical concepts and demonstrate how you can store and query embeddings in Azure SQL data to enhance your application with AI capabilities.

> [!IMPORTANT]  
> Vector Functions are in Public Preview. Learn the details about vectors in Azure SQL here: https://aka.ms/azure-sql-vector-public-preview

## Prerequisites

To use the provided samples make sure you have the following pre-requisites:

1. An Azure subscription - [Create one for free](https://azure.microsoft.com/pricing/purchase-options/azure-account)

1. Azure SQL Database - [Create one for free](https:/learn.microsoft.com/azure/azure-sql/database/free-offer?view=azuresql)

1. Make sure you have an [Azure OpenAI](https://learn.microsoft.com/azure/ai-services/openai/overview) resource created in your Azure subscription.

1. Make sure you have access to the Early Adopter Preview by filling out this form: https://aka.ms/azuresql-vector-eap

1. Azure Data Studio - [Download for free](https://learn.microsoft.com/azure-data-studio/download-azure-data-studio) to use the notebooks offline. [SQL Server Management Studio](https://learn.microsoft.com/sql/ssms/download-sql-server-management-studio-ssms) is also an option if you don't want to use notebook offline.

1. If you are going to clone this repository in your machine, make sure to have installed the `git-lfs` extension: [Git Large File Storage](https://git-lfs.com/)

## Samples  

### Getting Started

A simple getting started to get familiar with common vector functions is available here: [Getting-Started](./Getting-Started/getting-started.ipynb)

### Embeddings

Learn how to get embeddings from OpenAI directly from Azure SQL using the sample available the [Embeddings/T-SQL](./Embeddings/T-SQL) folder.

### Vector Search

The [Vector-Search](./Vector-Search) example illustrates the implementation of Vector Similarity Search within an SQL database, highlighting the capabilities of semantic search. By leveraging vector representations of text, the system can identify reviews that share contextual similarities with a given search query, transcending the limitations of keyword exact matches. Additionally, it demonstrates the integration of Keyword Search to guarantee the inclusion of specific terms within the search outcomes.

### Hybrid Search

The Python sample in the [Hybrid-Search](./Hybrid-Search/) folder shows how to combine Fulltext search in Azure SQL database with BM25 ranking and cosine similarity ranking to do hybrid search.

### Retrieval Augmented Generation

The RAG pattern is a powerful way to generate text using a pre-trained language model and a retrieval mechanism. The [Retrieval Augmented Generation](./Retrieval-Augmented-Generation) folder contains a sample that demonstrates how to use the RAG pattern with Azure SQL and Azure OpenAI, using Python notebooks.

### SQL Client

If you are using SQL Client directly in your applications, you can use the [SqlClient](./DotNet/SqlClient) folder to see how to use Native Vector Search in C#/.NET. 

### Entity Framework Core

If you are using .NET EF Core, you can use the [EF-Core](./DotNet/EF-Core) sample to see how to use the new vector functions in your application.

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
