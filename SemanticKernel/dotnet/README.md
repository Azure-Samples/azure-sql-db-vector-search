## Semantic Kernel 

Semantic Kernel is an SDK that integrates Large Language Models (LLMs) like OpenAI, Azure OpenAI, and Hugging Face with conventional programming languages like C#, Python, and Java. Semantic Kernel achieves this by allowing you to define plugins that can be chained together in just a few lines of code.

A plugin to use SQL Server and Azure SQL as a vector store is available here:

[Microsoft.SemanticKernel.Connectors.SqlServer](https://github.com/microsoft/semantic-kernel/tree/main/dotnet/src/VectorData/SqlServer)

Semantic Kernel provides native SQL Server support both for the [legacy Memory Store](https://learn.microsoft.com/semantic-kernel/concepts/vector-store-connectors/memory-stores/?pivots=programming-language-csharp) and the new [Vector Store](https://learn.microsoft.com/semantic-kernel/concepts/vector-store-connectors/?pivots=programming-language-csharp). Samples on how to use both are available in this repository:

- [Vector Store sample](./VectorStoreSample)
- [Memory Store (legacy) sample](./MemoryStoreSample)

## Getting Started

Create a `.env` file using the provided `.env.example` file as a template. Replace the values in `<>` with your own values. Then move into the folder with the sample you want to try and run application using the following command:

```bash
dotnet run
```

