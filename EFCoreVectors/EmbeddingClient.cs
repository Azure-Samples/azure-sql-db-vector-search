using Azure;
using Azure.AI.OpenAI;
using DotNetEnv;

namespace EFCoreVectors;

public interface IEmbeddingClient
{
    float[] GetEmbedding(string text);
}

public class AzureOpenAIEmbeddingClient: IEmbeddingClient
{
    static AzureKeyCredential credentials = new(Env.GetString("OPENAI_KEY"));
    static OpenAIClient openAIClient = new(new Uri(Env.GetString("OPENAI_URL")), credentials);

    public float[] GetEmbedding(string text)
    {
        Console.WriteLine($"-> Getting embedding for: {text}");
       
        EmbeddingsOptions embeddingsOptions = new()
        {
            DeploymentName = Env.GetString("OPENAI_DEPLOYMENT_NAME"),
            Input = { text },
        };
        
        Response<Embeddings> response = openAIClient.GetEmbeddings(embeddingsOptions);
        EmbeddingItem item = response.Value.Data[0];

        return item.Embedding.ToArray();
    }
}

public class MockEmbeddingClient: IEmbeddingClient
{
    public float[] GetEmbedding(string text)
    {
        return [1.0f, 2.0f, 3.0f];
    }   
}