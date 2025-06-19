# Azure Resource Deployment for Retrieval-Augmented Generation (RAG)

This repository provides ARM templates to deploy all required Azure resources for building Retrieval-Augmented Generation (RAG) pipelines. It supports both structured and unstructured data scenarios and is designed to simplify user onboarding when creating GenAI applications. The template includes the deployment of Azure SQL Database, Azure Document Intelligence resource, Azure OpenAI resources, and models from AI Foundry.  

## Prerequisites
Before deploying the template, ensure you have the following:

- An active **Azure for Students** subscription
- Permissions to create resources in the selected resource group
- Sufficient quota for Azure OpenAI resources 


## Deploy to Azure

### 🔹 RAG for Structured Data

Use this template if your data is stored in structured formats such as .csv file.  
[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2FKushagra-2000%2FARM_SQL_OpenAI%2Frefs%2Fheads%2Fmain%2FRAG_deployment.json)

---

### 🔸 RAG for Unstructured Documents

Use this template if your data consists of PDFs, scanned documents, or other unstructured formats.  
[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2FKushagra-2000%2FARM_SQL_OpenAI%2Frefs%2Fheads%2Fmain%2FRAG_unstructured_deployment.json)

### Parameters Description
| Parameter Name  | Description | Example |
| :---------------: | :------------- | :-------: |
| `serverName`  | Name of the Azure SQL Server (logical server) to host your database. | Sample-SQL-server
| `sqlDBName`  | Name of the SQL database to be created.  | Sample-SQL-Database
| `location`  | Azure region for all resources. Recommended to keep the default.  | eastus2
|`administratorLogin` | The administrator username of the SQL server for SQL authentication.  |   |
| `administratorLoginPassword`  | The administrator password of the SQL server for SQL authentication. |  |   
| `OpenAI_account_name`  | Name of the Azure OpenAI resource.  | Sample-OpenAI-resource
| `OpenAI_account_location`  | Region for the Azure OpenAI resource  | eastus2
| `OpenAI_chat_completion_model`  | Chat model to deploy. | gpt-4.1
| `embedding_model`	  | Embedding model for vector search.  | text-embedding-3-small
| `Document_Intelligence_account_name` | Name of the Azure Document Intelligence (Form Recognizer) resource. | sample-doc-intel          
  
⚠️ Note: This is a demo deployment. `The default server name (sample-sqlserver) may already exist in your region`, which can cause deployment errors. To avoid this, please customize the server (or resource) name by appending your name or initials.   
If you encounter an error, simply re-deploy with a unique resource name.  

## Firewall Configuration
**Note:** After the deployment is completed successfully, you need to configure the firewall settings for the **SQL server** separately to allow access from your client IP addresses.

1. Go to the deployed SQL Server in the Azure Portal.
2. Navigate to **Security > Networking > Virtual networks**.
3. Add your client IP and click Save.

## Clean Up Resources
When you're finished using these resources, or if you want to start over again with a new free database (limit 10 per subscription), you can delete the resource group you created, which deletes all the resources within it.

To delete `myResourceGroup` and all its resources using the Azure portal:

1. In the Azure portal, search for and select Resource groups, and then select `myResourceGroup` from the list.
2. On the Resource group page, select Delete resource group.
3. Under Type the resource group name, enter `myResourceGroup`, and then select Delete.

## Troubleshooting
If you encounter any issues during deployment, check the following:

- Ensure you have sufficient quota for Azure OpenAI resources.
- Verify that all parameters are correctly specified.
- Check the deployment logs in the Azure Portal for detailed error messages.

## Resources
For guidelines and information on any specific resource, check out the following microsoft documentation:

- 📄 [Deploy Azure SQL Database for free](https://learn.microsoft.com/en-us/azure/azure-sql/database/free-offer?view=azuresql)
- 📄 [Create a Document Intelligence resource](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/how-to-guides/create-document-intelligence-resource?view=doc-intel-4.0.0#get-endpoint-url-and-keys)
- 📄 [Create and deploy an Azure OpenAI Service resource](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/create-resource?pivots=web-portal)
