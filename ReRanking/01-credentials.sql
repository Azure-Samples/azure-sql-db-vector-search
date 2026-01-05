/*
    Define credentials to access Azure OpenAI
*/

-- Store API Key. IT is recommended to use Managed Identity instead, as explained here: 
-- https://devblogs.microsoft.com/azure-sql/go-passwordless-when-calling-azure-openai-from-azure-sql-using-managed-identities/
CREATE DATABASE SCOPED CREDENTIAL [https://<your-endpoint>.services.ai.azure.com/providers/cohere/v2/rerank]
WITH IDENTITY = 'HTTPEndpointHeaders',
SECRET = '{"Api-Key": "<your-api-key>"}'

