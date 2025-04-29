using System.Text;
using Microsoft.SemanticKernel;
using Microsoft.SemanticKernel.ChatCompletion;
using Microsoft.SemanticKernel.Connectors.OpenAI;
using Microsoft.SemanticKernel.Connectors.SqlServer;
using Microsoft.SemanticKernel.Memory;
using DotNetEnv;
using System.Data.Common;
using Microsoft.SemanticKernel.Embeddings;

Env.Load();

#pragma warning disable SKEXP0001, SKEXP0010, SKEXP0020

string azureOpenAIEndpoint = Env.GetString("AZURE_OPENAI_ENDPOINT")!;
string azureOpenAIApiKey = Env.GetString("AZURE_OPENAI_API_KEY")!;
string embeddingModelDeploymentName = Env.GetString("AZURE_OPENAI_EMBEDDING_MODEL")!;
string chatModelDeploymentName = Env.GetString("AZURE_OPENAI_CHAT_MODEL")!;
string connectionString = Env.GetString("AZURE_SQL_CONNECTION_STRING")!;
string tableName = "SemanticKernel_Memory";

Console.WriteLine("Creating Semantic Kernel services...");
var kernel = Kernel.CreateBuilder()
    .AddAzureOpenAIChatCompletion(chatModelDeploymentName, azureOpenAIEndpoint, azureOpenAIApiKey)
    .AddAzureOpenAITextEmbeddingGeneration(embeddingModelDeploymentName, azureOpenAIEndpoint, azureOpenAIApiKey)
    .Build();

var textEmbeddingGenerationService = kernel.GetRequiredService<ITextEmbeddingGenerationService>();

Console.WriteLine("Connecting to Memory Store...");
var memory = new MemoryBuilder()
    .WithSqlServerMemoryStore(connectionString)        
    .WithTextEmbeddingGeneration(textEmbeddingGenerationService)
    .Build();

Console.WriteLine("Adding memories...");
await memory.SaveInformationAsync(tableName, id: "semantic-kernel-mssql", text: "With the new connector Microsoft.SemanticKernel.Connectors.SqlServer it is possible to efficiently store and retrieve memories thanks to the newly added vector support");
await memory.SaveInformationAsync(tableName, id: "semantic-kernel-azuresql", text: "At the moment Microsoft.SemanticKernel.Connectors.SqlServer can be used only with Azure SQL");
await memory.SaveInformationAsync(tableName, id: "azuresql-vector-1", text: "Azure SQL support for vectors is in Public Preview and can be used by anyone in Azure right away");
await memory.SaveInformationAsync(tableName, id: "pizza-favourite-food", text: "Pizza is one of the favourite food in the world.");

Console.WriteLine("You can now chat with the AI chatbot.");
Console.WriteLine("Sample question: Can I use vector with Azure SQL?");
Console.WriteLine("");

var ai = kernel.GetRequiredService<IChatCompletionService>();
var chatHistory = new ChatHistory("You are an AI assistant that helps people find information. Only use the information provided in the memory to answer the questions. Do not make up any information.");
var consoleMessages = new StringBuilder();
while (true)
{
    Console.Write("Question: ");
    var question = Console.ReadLine()!;

    Console.WriteLine("\nSearching information from the memory...");
    consoleMessages.Clear();
    await foreach (var result in memory.SearchAsync(tableName, question, limit: 3))
    {        
        consoleMessages.AppendLine(result.Metadata.Text);
    }
    if (consoleMessages.Length != 0) {
        Console.WriteLine("\nFound information from the memory:");
        Console.WriteLine(consoleMessages.ToString());
    }

    Console.WriteLine("Answer: ");
    var contextToRemove = -1;
    if (consoleMessages.Length != 0)
    {
        consoleMessages.Insert(0, "Here's some additional information: ");
        contextToRemove = chatHistory.Count;
        chatHistory.AddUserMessage(consoleMessages.ToString());
    }

    chatHistory.AddUserMessage(question);

    consoleMessages.Clear();
    await foreach (var message in ai.GetStreamingChatMessageContentsAsync(chatHistory))
    {
        Console.Write(message);
        consoleMessages.Append(message.Content);
    }
    Console.WriteLine();
    chatHistory.AddAssistantMessage(consoleMessages.ToString());

    if (contextToRemove >= 0)
        chatHistory.RemoveAt(contextToRemove);

    Console.WriteLine();
}
