# Native Vector Support in Azure SQL and SQL Server

This repo hosts samples meant to help use the new **Native Vector Support in Azure SQL DB** feature. We illustrate key technical concepts and demonstrate how you can store and query embeddings in Azure SQL data to enhance your application with AI capabilities.

**Note**: These functions are in preview and is subject to change. Preview features are not meant for production use and are subject to additional terms of use.

## Prerequisites

1. An Azure subscription - [Create one for free](https://azure.microsoft.com/pricing/purchase-options/azure-account)

2. Azure SQL Database - [Create one for free](https:/learn.microsoft.com/azure/azure-sql/database/free-offer?view=azuresql)

3. Make sure you have an [Azure OpenAI](https://learn.microsoft.com/azure/ai-services/openai/overview) resource created in your Azure subscription.

## Samples  

### Embeddings

Learn how to get embeddings from OpenAI directly from Azure SQL using the sample available the [`Embeddings/T-SQL`](./Embeddings/T-SQL) folder.

### Vector Search

Coming soon

### Hybrid Search

The Python sample in the [`Hybrid-Search`](./Hybrid-Search/) folder shows how to combine Fulltext search in Azure SQL database with BM25 ranking and cosine similarity ranking to do hybrid search.

## Resources

- [Create and deploy an Azure OpenAI Service resource](https://learn.microsoft.com/azure/ai-services/openai/how-to/create-resource?pivots=web-portal)
- [Embeddings models](https://learn.microsoft.com/azure/ai-services/openai/concepts/models#embeddings-models)
- [SQL AI Samples and Examples](https://aka.ms/sqlaisamples)
- [Frequently asked questions about Copilot in Azure SQL Database (preview)](https://learn.microsoft.com/azure/azure-sql/copilot/copilot-azure-sql-faq?view=azuresql)
- [Responsible AI FAQ for Microsoft Copilot for Azure (preview)](https://learn.microsoft.com/azure/copilot/responsible-ai-faq)

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft trademarks or logos is subject to and must follow [Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualproperty/trademarks/usage/general). Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship. Any use of third-party trademarks or logos are subject to those third-party's policies.
