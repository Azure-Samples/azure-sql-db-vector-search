metadata description = 'Create Azure SQL Server and Database with Azure AD-only authentication.'

param serverName string
param databaseName string
param location string = resourceGroup().location
param tags object = {}

@description('Object ID of the Azure AD user to set as SQL Server administrator.')
param aadAdminObjectId string

@description('Principal ID of the managed identity for role assignments.')
param managedIdentityPrincipalId string = ''

resource sqlServer 'Microsoft.Sql/servers@2023-08-01-preview' = {
  name: serverName
  location: location
  tags: tags
  properties: {
    // Azure AD-only authentication — no SQL auth passwords
    administrators: {
      administratorType: 'ActiveDirectory'
      principalType: 'User'
      login: 'aad-admin'
      sid: aadAdminObjectId
      tenantId: tenant().tenantId
      azureADOnlyAuthentication: true
    }
    minimalTlsVersion: '1.2'
  }
}

// Allow Azure services (including Azure OpenAI, managed identities) to connect
resource firewallAllowAzure 'Microsoft.Sql/servers/firewallRules@2023-08-01-preview' = {
  parent: sqlServer
  name: 'AllowAllWindowsAzureIps'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource sqlDatabase 'Microsoft.Sql/servers/databases@2023-08-01-preview' = {
  parent: sqlServer
  name: databaseName
  location: location
  tags: tags
  sku: {
    name: 'S0'
    tier: 'Standard'
  }
}

// SQL Server Contributor role for managed identity (management plane access)
// Data plane access (query/insert) requires T-SQL GRANT after deployment.
var sqlServerContributorRole = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '6d8ee4ec-f05a-4a1d-8b00-a9b17e38b437'
)

resource managedIdentityRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(managedIdentityPrincipalId)) {
  name: guid(sqlServer.id, managedIdentityPrincipalId, sqlServerContributorRole)
  scope: sqlServer
  properties: {
    roleDefinitionId: sqlServerContributorRole
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output fullyQualifiedDomainName string = sqlServer.properties.fullyQualifiedDomainName
output serverName string = sqlServer.name
output databaseName string = sqlDatabase.name
