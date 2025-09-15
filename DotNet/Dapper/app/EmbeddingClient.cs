using Azure;
using Azure.AI.OpenAI;
using Azure.Identity;
using DotNetEnv;

namespace DapperVectors;

public interface IEmbeddingClient
{
    float[] GetEmbedding(string text, int dimensions = 1536);
}

public class AzureOpenAIEmbeddingClient : IEmbeddingClient
{
    static readonly AzureOpenAIClient aiClient;

    static AzureOpenAIEmbeddingClient()
    {
        var endpoint = new Uri(Env.GetString("OPENAI_URL"));

        aiClient = Env.GetString("OPENAI_KEY") switch
        {
            null or "" => new AzureOpenAIClient(endpoint, new DefaultAzureCredential()),
            string key => new AzureOpenAIClient(endpoint, new AzureKeyCredential(key)),
        };
    }

    public float[] GetEmbedding(string text, int dimensions = 1536)
    {
        Console.WriteLine($"-> Getting embedding for: {text}");

        var embeddingClient = aiClient.GetEmbeddingClient(Env.GetString("OPENAI_DEPLOYMENT_NAME"));
        var embedding = embeddingClient.GenerateEmbedding(text, new() { Dimensions = dimensions });
        var vector = embedding.Value.ToFloats().ToArray();

        if (vector.Length != dimensions)
        {
            throw new Exception($"Expected {dimensions} dimensions, but got {vector.Length}");
        }

        return vector;
    }
}

public class MockEmbeddingClient : IEmbeddingClient
{
    public float[] GetEmbedding(string text, int dimensions = 1536)
    {
        Random random = new();
        return Enumerable.Range(0, dimensions).Select(_ => (float)random.NextDouble()).ToArray();
    }
}
