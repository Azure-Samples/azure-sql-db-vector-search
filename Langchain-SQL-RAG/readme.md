# Building AI-powered apps on Azure SQL Database using LLMs and LangChain

Azure SQL Database now supports native vector search capabilities, bringing the power of vector search operations directly to your SQL databases. You can read the full announcement of the public preview [here](https:\devblogs.microsoft.com\azure-sql\exciting-announcement-public-preview-of-native-vector-support-in-azure-sql-database\)

We are also thrilled to announce the release of [langchain-sqlserver](https:\pypi.org\project\langchain-sqlserver\) version 0.1.1. You can use this package to manage Langchain vectorstores in SQL Server. This new release brings enhanced capabilities by parsing both ODBC connection strings and SQLAlchemy format connection strings, making it easier than ever to integrate with Azure SQL DB

In this step-by-step tutorial, we will show you how to add generative AI features to your own applications with just a few lines of code using Azure SQL DB, [LangChain](https:\pypi.org\project\langchain-sqlserver\), and LLMs.

## Dataset

The Harry Potter series, written by J.K. Rowling, is a globally beloved collection of seven books that follow the journey of a young wizard, Harry Potter, and his friends as they battle the dark forces led by the evil Voldemort. Its captivating plot, rich characters, and imaginative world have made it one of the most famous and cherished series in literary history. 

This Sample dataset from [Kaggle](https:\www.kaggle.com\datasets\shubhammaindola\harry-potter-books) contains 7 .txt files of 7 books of Harry Potter. For this demo we will only be using the first book - Harry Potter and the Sorcerer's Stone.

In this notebook, we will showcase two exciting use cases:
1. A sample Python application that can understand and respond to human language queries about the data stored in your Azure SQL Database. This **Q&A system** leverages the power of SQL Vectore Store & LangChain to provide accurate and context-rich answers from the Harry Potter Book.
1. Next, we will push the creative limits of the application by teaching it to generate new AI-driven **Harry Potter fan fiction** based on our existing dataset of Harry Potter books. This feature is sure to delight Potterheads, allowing them to explore new adventures and create their own magical stories.

## Prerequisites

- **Azure Subscription**: [Create one for free](https:\azure.microsoft.com\free\cognitive-services?azure-portal=true)
    
- **Azure SQL Database**: [Set up your database for free](https:\learn.microsoft.com\azure\azure-sql\database\free-offer?view=azuresql)
    
- **Azure OpenAI Access**: Apply for access in the desired Azure subscription at [https://aka.ms/oai/access](https:\aka.ms\oai\access)
    
- **Azure OpenAI Resource**: Deploy an embeddings model (e.g., `text-embedding-small` or `text-embedding-ada-002`) and a `GPT-4.0` model for chat completion. Refer to the [resource deployment guide](https:\learn.microsoft.com\azure\ai-services\openai\how-to\create-resource) 

- **Azure Blob Storage** Deploy a Azure [Blob Storage Account](https:\learn.microsoft.com\azure\storage\blobs\storage-quickstart-blobs-portal) to upload your dataset
    
- **Python**: Version 3.7.1 or later from Python.org. (Sample has been tested with Python 3.11)
    
- **Python Libraries**: Install the required libraries from the requirements.txt
    
- **Jupyter Notebooks**: Use within [Azure Data Studio](https:\learn.microsoft.com\en-us\azure-data-studio\notebooks\notebooks-guidance) or Visual Studio Code .
    

## Getting Started

1. **Model Deployment**: Deploy an embeddings model (`text-embedding-small` or `text-embedding-ada-002`) and a `GPT-4` model for chat completion. Note the 2 models deployment names for use in the `.env` file

![Deployed OpenAI Models](..\Assets\modeldeployment.png)

2. **Connection String**: Find your Azure SQL DB connection string in the Azure portal under your database settings.
3. **Configuration**: Populate the `.env` file with your SQL server connection details , Azure OpenAI key and endpoint , api-version & Model deploymentname

You can retrieve the Azure OpenAI _endpoint_ and _key_:

![Azure OpenAI Endpoint and Key](..\Assets\endpoint.png)

4. **Upload dataset** In your [Blob Storage Account](https:\learn.microsoft.com\en-us\azure\storage\blobs\storage-quickstart-blobs-portal) create a container and upload the .txt file using the steps [here](https:\learn.microsoft.com\azure\storage\blobs\storage-quickstart-blobs-portal)

## Running the Notebook

To [execute the notebook](https:\learn.microsoft.com\azure-data-studio\notebooks\notebooks-python-kernel), connect to your Azure SQL database using Azure Data Studio, which can be downloaded [here](https:\azure.microsoft.com\products\data-studio)