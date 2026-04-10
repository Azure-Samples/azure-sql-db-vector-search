targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment which is used to generate a short unique hash used in all resources.')
param environmentName string

@minLength(1)
@description('Location for all resources')
// https://learn.microsoft.com/azure/ai-services/openai/concepts/models?tabs=python-secure%2Cglobal-standard%2Cstandard-chat-completions#models-by-deployment-type
@allowed([
  'eastus2'
  'swedencentral'
])
@metadata({
  azd: {
    type: 'location'
  }
})
param location string

@description('Id of the principal to assign database and application roles.')
param deploymentUserPrincipalId string = ''

var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = { 'azd-env-name': environmentName }
var prefix = '${environmentName}${resourceToken}'

// Azure OpenAI model configuration
//
// QUOTA REQUIREMENT: The embedding model below requires available quota in the
// target region (eastus2 or swedencentral). If deployment fails with
// "InsufficientQuota" or "The specified capacity ... is not available", try:
//   1. A different allowed region (change the @allowed list above)
//   2. A different SKU (e.g., swap 'Standard' ↔ 'GlobalStandard')
//   3. Requesting a quota increase in the Azure Portal under
//      Subscriptions > Resource providers > Microsoft.CognitiveServices > Quotas

// Embedding model: text-embedding-3-small, version 1, deployed as Standard
// This is the model used by all language samples to generate 1536-dimension vectors.
var embeddingModelName = 'text-embedding-3-small'
var embeddingModelVersion = '1'
var embeddingModelSkuName = 'Standard'
var embeddingModelCapacity = 10

// Note: No chat model is needed for the vector search quickstart (embedding only).
// If a chat model is added later, use gpt-4.1-mini (version 2025-04-14, Standard).
// gpt-4o-mini Standard was deprecated 2026-03-31; use gpt-4.1-mini instead.

// SQL Database configuration
var sqlDatabaseName = 'vectordb'

// Organize resources in a resource group
resource resourceGroup 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: '${environmentName}-${resourceToken}-rg'
  location: location
  tags: tags
}

module managedIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.4.0' = {
  name: 'user-assigned-identity'
  scope: resourceGroup
  params: {
    name: 'managed-identity-${prefix}'
    location: location
    tags: tags
  }
}

var openAiServiceName = 'openai-${prefix}'
module openAi 'br/public:avm/res/cognitive-services/account:0.7.1' = {
  name: 'openai'
  scope: resourceGroup
  params: {
    name: openAiServiceName
    location: location
    tags: tags
    kind: 'OpenAI'
    sku: 'S0'
    customSubDomainName: openAiServiceName
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
    deployments: [
      {
        name: embeddingModelName
        model: {
          format: 'OpenAI'
          name: embeddingModelName
          version: embeddingModelVersion
        }
        sku: {
          name: embeddingModelSkuName
          capacity: embeddingModelCapacity
        }
      }
    ]
    roleAssignments: concat(
      [
        {
          principalId: managedIdentity.outputs.principalId
          roleDefinitionIdOrName: 'Cognitive Services OpenAI User'
        }
      ],
      !empty(deploymentUserPrincipalId)
        ? [
            {
              principalId: deploymentUserPrincipalId
              roleDefinitionIdOrName: 'Cognitive Services OpenAI User'
            }
          ]
        : []
    )
  }
}

module sqlDatabase './sql-database.bicep' = {
  name: 'sql-database'
  scope: resourceGroup
  params: {
    serverName: 'sql-${prefix}'
    databaseName: sqlDatabaseName
    location: location
    tags: tags
    aadAdminObjectId: deploymentUserPrincipalId
    managedIdentityPrincipalId: managedIdentity.outputs.principalId
  }
}

// General outputs
output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_RESOURCE_GROUP string = resourceGroup.name

// Azure OpenAI outputs
output AZURE_OPENAI_ENDPOINT string = openAi.outputs.endpoint
output AZURE_OPENAI_EMBEDDING_MODEL string = embeddingModelName
output AZURE_OPENAI_EMBEDDING_DEPLOYMENT string = embeddingModelName

// Azure SQL outputs
output AZURE_SQL_SERVER string = sqlDatabase.outputs.fullyQualifiedDomainName
output AZURE_SQL_DATABASE string = sqlDatabaseName
