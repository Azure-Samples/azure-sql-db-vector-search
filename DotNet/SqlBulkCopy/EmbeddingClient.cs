using Azure;
using Azure.AI.OpenAI;
using DotNetEnv;

public interface IEmbeddingClient
{
    float[] GetEmbedding(string text, int dimensions);
}

public class AzureOpenAIEmbeddingClient: IEmbeddingClient
{
    static readonly AzureKeyCredential credentials = new(Env.GetString("OPENAI_KEY"));
    static readonly AzureOpenAIClient aiClient = new(new Uri(Env.GetString("OPENAI_URL")), credentials);

    public float[] GetEmbedding(string text, int dimensions = 1536)
    {
        Console.WriteLine($"-> Getting embedding for: {text}");
        
        var embeddingClient = aiClient.GetEmbeddingClient(Env.GetString("OPENAI_DEPLOYMENT_NAME"));        
                       
        var embedding = embeddingClient.GenerateEmbedding(text, new() { Dimensions = dimensions });        

        var vector = embedding.Value.ToFloats().ToArray();
        if (vector.Length != dimensions) {
            throw new Exception($"Expected {dimensions} dimensions, but got {vector.Length}");
        }

        return vector;
    }
}

public class MockEmbeddingClient: IEmbeddingClient
{
    public float[] GetEmbedding(string text, int dimensions = 1536)
    {
        Random random = new();
        return [.. Enumerable.Range(0, dimensions).Select(_ => (float)random.NextDouble())];
    }   
}
