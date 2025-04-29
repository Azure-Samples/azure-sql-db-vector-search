## Semantic Kernel 

Semantic Kernel is an SDK that integrates Large Language Models (LLMs) like OpenAI, Azure OpenAI, and Hugging Face with conventional programming languages like C#, Python, and Java. Semantic Kernel achieves this by allowing you to define plugins that can be chained together in just a few lines of code.

A plugin to use SQL Server and Azure SQL as a vector store is available here:

https://github.com/microsoft/semantic-kernel/tree/main/dotnet/src/Connectors/Connectors.Memory.SqlServer

> [!IMPORTANT]  
> The features needed to use this connector are available in preview in Azure SQL only at the moment. Please take a look at the [Public Preview of Native Vector Support in Azure SQL Database](https://devblogs.microsoft.com/azure-sql/exciting-announcement-public-preview-of-native-vector-support-in-azure-sql-database/) for more information.

Semantic Kernel provides native SQL Server support both for the [legacy Memory Store](https://learn.microsoft.com/semantic-kernel/concepts/vector-store-connectors/memory-stores/?pivots=programming-language-csharp) and the new [Vector Store](https://learn.microsoft.com/semantic-kernel/concepts/vector-store-connectors/?pivots=programming-language-csharp). Samples on how to use both are available in this repository:

- [Vector Store sample](./VectorStoreSample)
- [Memory Store (legacy) sample](./MemoryStoreSample)

## Getting Started

Create a `.env` file using the provided `.env.example` file as a template. Replace the values in `<>` with your own values. Then move into the folder with the sample you want to try and run application using the following command:

```bash
dotnet run
```

