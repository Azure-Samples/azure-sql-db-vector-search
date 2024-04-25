# Store and query OpenAI embeddings in Azure SQL DB (TSQL)

### **Vector Similarity search in SQL DB.**

We will be using a SQL notebook to demonstrate how to perform Vector Similarity Search in SQL DB.

You can run the following notebook using the [SQL Kernel for Notebooks in Azure Data Studio](https://learn.microsoft.com/en-us/azure-data-studio/notebooks/notebooks-guidance#connect-to-a-kernel). 

- Data set used : [Fine Foods Review Dataset]([AzureSQLVectorSearch/Dataset/Reviews.csv](https://github.com/Azure-Samples/azure-sql-db-vector-search/blob/ee517d7e6e2969e1a71aa69f51db762a02af30a1/AzureSQLVectorSearch/Dataset/Reviews.csv))  <span style="background:white">is available on Kaggle. This dataset consists of reviews of fine foods from amazon.</span>
- For this tutorial to demonstrate storing and querying vectors in SQL we will be using a smaller sample of   [finefoodembeddings.csv]([AzureSQLVectorSearch/Dataset/finefoodembeddings.csv](https://github.com/Azure-Samples/azure-sql-db-vector-search/blob/1e47abf564caa0519c823fff0761fd005ca8bbc0/AzureSQLVectorSearch/Dataset/finefoodembeddings.csv))  file that contains already generated embeddings using text-embedding-small model from Azure OpenAI. If you want to learn how to generate embeddings using Azure Open AI for your data , take a look at the tutorial here.
    
    ### <span style="color: var(--vscode-foreground);"><b>Prerequisites:</b></span>
    
    - An Azure subscription - [Create one for free](https:\github.com\Azure-Samples\azure-sql-db-vector-search\blob\622f7be47cafa261b267163a9a94af13d4fa9243\AzureSQLVectorSearch\src\https:\azure.microsoft.com\free\cognitive-services?azure-portal=true)
    - Azure SQL Database - [Create one for free](https:\github.com\Azure-Samples\azure-sql-db-vector-search\blob\622f7be47cafa261b267163a9a94af13d4fa9243\AzureSQLVectorSearch\src\https:\learn.microsoft.com\azure\azure-sql\database\free-offer?view=azuresql)
    - [Azure Data Studio](https:\azure.microsoft.com\products\data-studio\) to connect to an Azure SQL database. 
    - Make sure you have an [Azure OpenAI](https:\learn.microsoft.com\en-us\azure\ai-services\openai\overview) resource created in your Azure subscription. For this specific sample you have to deploy an Embedding model using the **text-embedding-small** model, the same used for the source we are using in this sample. Once that is done, you need to get the API KEY and the URL of the deployed model  [Embeddings REST API](https:\learn.microsoft.com\azure\cognitive-services\openai\reference#embeddings). And then you can use the    [sp\_invoke\_external\_rest\_endpoint](https:\learn.microsoft.com\sql\relational-databases\system-stored-procedures\sp-invoke-external-rest-endpoint-transact-sql?view=azuresqldb-current) to call the REST API from Azure SQL database.


    ### **Importing the data into SQLDB**

Import the data from the [finefoodembeddings.csv]([AzureSQLVectorSearch/Dataset/finefoodembeddings.csv](https://github.com/Azure-Samples/azure-sql-db-vector-search/blob/1e47abf564caa0519c823fff0761fd005ca8bbc0/AzureSQLVectorSearch/Dataset/finefoodembeddings.csv)) to the finefoodreviews table.

You can use the [SQL Server Import extension](https:\learn.microsoft.com\en-us\azure-data-studio\extensions\sql-server-import-extension) available in the [Azure Data Studio](https:\azure.microsoft.com\products\data-studio\) that converts .txt and .csv files into a SQL table . The step by the step instructions to do this can be found  [here](https:\learn.microsoft.com\en-us\azure-data-studio\extensions\sql-server-import-extension)<span style="font-size:12.0pt;font-family:&quot;Segoe UI&quot;,sans-serif;mso-fareast-font-family:
&quot;Times New Roman&quot;;color:#161616;background:white;mso-font-kerning:0pt;
mso-ligatures:none;mso-fareast-language:EN-IN">.</span>

<span style="color: var(--vscode-foreground);">You will need to <b>change the datatypes</b> to the following in the GUI window</span>

<span style="font-family:&quot;Calibri&quot;,sans-serif;color:black;mso-color-alt:windowtext"><br></span>

<span style="color: #0000ff;">CREATE</span> <span style="color: #0000ff;">TABLE</span> \[dbo\].\[finefoodreviews\](

    \[Id\] \[bigint\] <span style="color: #0000ff;">NOT NULL</span>,

    \[Time\] \[nvarchar\](<span style="color: #09885a;">50</span>) <span style="color: #0000ff;">NULL</span>,

    \[ProductId\] \[nvarchar\](<span style="color: #09885a;">500</span>) <span style="color: #0000ff;">NULL</span>,

    \[UserId\] \[nvarchar\](<span style="color: #09885a;">50</span>) <span style="color: #0000ff;">NULL</span>,

    \[Score\] \[bigint\] <span style="color: #0000ff;">NULL</span>,

    \[Summary\] \[nvarchar\](max) <span style="color: #0000ff;">NULL</span>,

    \[Text\] \[nvarchar\](max) <span style="color: #0000ff;">NULL</span>,

    \[combined\] \[nvarchar\](max) <span style="color: #0000ff;">NULL</span>,

    \[vector\] \[nvarchar\](<span style="color: #09885a;">max</span>) <span style="color: #0000ff;">NULL</span>

) <span style="color: #0000ff;">ON</span> \[PRIMARY\] <span style="color: #0000ff;">TEXTIMAGE_ON</span> \[PRIMARY\]

<span style="color: #0000ff;">GO</span>
