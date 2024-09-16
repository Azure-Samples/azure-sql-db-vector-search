# Leveraging Azure SQL DB’s Native Vector Capabilities for Enhanced Resume Matching with Azure Document Intelligence and RAG

In this tutorial, we will explore how to leverage Azure SQL DB’s new vector data type to store embeddings and perform similarity searches using built-in vector functions, enabling advanced resume matching to identify the most suitable candidates. 

By extracting and chunking content from PDF resumes using Azure Document Intelligence, generating embeddings with Azure OpenAI, and storing these embeddings in Azure SQL DB, we can perform sophisticated vector similarity searches and retrieval-augmented generation (RAG) to identify the most suitable candidates based on their resumes.

### **Tutorial Overview**

- This Python notebook will teach you to:
    1. **Chunk PDF Resumes**: Use **`Azure Document Intelligence`** to extract and chunk content from PDF resumes.
    2. **Create Embeddings**: Generate embeddings from the chunked content using the **`Azure OpenAI API`**.
    3. **Vector Database Utilization**: Store embeddings in **`Azure SQL DB`** utilizing the **`new Vector Data Type`** and perform similarity searches using built-in vector functions to find the most suitable candidates.
    4. **LLM Generation Augmentation**: Enhance language model generation with embeddings from a vector database. In this case, we use the embeddings to inform a GPT-4 chat model, enabling it to provide rich, context-aware answers about candidates based on their resumes

## Dataset

We use a sample dataset from [Kaggle](https:/www.kaggle.com/datasets/snehaanbhawal/resume-dataset) containing PDF resumes for this tutorial. For the purpose of this tutorial we will use 120 resumes from the **Information-Technology** folder

## Prerequisites

- **Azure Subscription**: [Create one for free](https:/azure.microsoft.com/free/cognitive-services?azure-portal=true)
- **Azure SQL Database**: [Set up your database for free](https:/learn.microsoft.com/azure/azure-sql/database/free-offer?view=azuresql)
- **Azure Document Intelligence** [Create a FreeAzure Doc Intelligence resource](https:/learn.microsoft.com/azure/ai-services/document-intelligence/create-document-intelligence-resource?view=doc-intel-4.0.0)
- **Azure Data Studio**: Download [here](https:/azure.microsoft.com/products/data-studio) to manage your Azure SQL database and [execute the notebook](https:/learn.microsoft.com/azure-data-studio/notebooks/notebooks-python-kernel)

## Additional Requirements for Embedding Generation

- **Azure OpenAI Access**: Apply for access in the desired Azure subscription at [https://aka.ms/oai/access](https:\aka.ms\oai\access)
- **Azure OpenAI Resource**: Deploy an embeddings model (e.g., `text-embedding-small` or `text-embedding-ada-002`) and a `GPT-4.0` model for chat completion. Refer to the [resource deployment guide](https:/learn.microsoft.com/azure/ai-services/openai/how-to/create-resource)
- **Python**: Version 3.7.1 or later from Python.org. (Sample has been tested with Python 3.11)
- **Python Libraries**: Install the required libraries openai, num2words, matplotlib, plotly, scipy, scikit-learn, pandas, tiktoken, and pyodbc.
- **Jupyter Notebooks**: Use within [Azure Data Studio](https:/learn.microsoft.com/en-us/azure-data-studio/notebooks/notebooks-guidance) or Visual Studio Code .

Code snippets are adapted from the [Azure OpenAI Service embeddings Tutorial](https:/learn.microsoft.com/en-us/azure/ai-services/openai/tutorials/embeddings?tabs=python-new%2Ccommand-line&pivots=programming-language-python)

## Getting Started

1. **Database Setup**: Execute SQL commands from the `createtable.sql` script to create the necessary table in your database.
2. **Model Deployment**: Deploy an embeddings model (`text-embedding-small` or `text-embedding-ada-002`) and a `GPT-4` model for chat completion. Note the 2 models deployment names for later use.

![Deployed OpenAI Models](..\Assets\modeldeployment.png)

3. **Connection String**: Find your Azure SQL DB connection string in the Azure portal under your database settings.
4. **Configuration**: Populate the `.env` file with your SQL server connection details , Azure OpenAI key and endpoint, Azure Document Intelligence key and endpoint values.

You can retrieve the Azure OpenAI _endpoint_ and _key_:

![Azure OpenAI Endpoint and Key](..\Assets\endpoint.png)

You can [retrieve](https:\learn.microsoft.com\azure\ai-services\document-intelligence\create-document-intelligence-resource?view=doc-intel-4.0.0#get-endpoint-url-and-keys) the Document Intelligence _endpoint_ and _key_:

![Azure Document Intelligence Endpoint and Key](..\Assets\docintelendpoint.png)

## Running the Notebook

To [execute the notebook](https:\learn.microsoft.com\azure-data-studio\notebooks\notebooks-python-kernel), connect to your Azure SQL database using Azure Data Studio, which can be downloaded [here](https:\azure.microsoft.com\products\data-studio)
