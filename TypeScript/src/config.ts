export interface AppConfig {
  azureSqlServer: string;
  azureSqlDatabase: string;
  azureOpenAiEndpoint: string;
  azureOpenAiEmbeddingDeployment: string;
}

export function loadConfig(): AppConfig {
  const required = (key: string): string => {
    const value = process.env[key];
    if (!value) {
      throw new Error(
        `Missing required environment variable: ${key}. ` +
          "Copy sample.env to .env and fill in your values."
      );
    }
    return value;
  };

  return {
    azureSqlServer: required("AZURE_SQL_SERVER"),
    azureSqlDatabase: required("AZURE_SQL_DATABASE"),
    azureOpenAiEndpoint: required("AZURE_OPENAI_ENDPOINT"),
    azureOpenAiEmbeddingDeployment: required(
      "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
    ),
  };
}
