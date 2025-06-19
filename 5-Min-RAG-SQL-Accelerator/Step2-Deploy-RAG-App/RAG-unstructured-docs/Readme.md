# RAG Streamlit App with Azure SQL DB on Structured Dataset

## Objective
This Streamlit app demonstrates how to build a Retrieval-Augmented Generation (RAG) solution for resume matching using Azure SQL Database's native vector capabilities, Azure Document Intelligence, and Azure OpenAI. The app enables users to upload PDF resumes, extract and chunk their content, generate embeddings, store/query them in Azure SQL DB, and perform LLM-powered Q&A for candidate search and recommendations.

## Key Features
- **PDF Resume Upload & Processing:** Upload multiple PDF resumes and extract text using Azure Document Intelligence.
- **Text Chunking:** Automatically split extracted text into manageable chunks (500 tokens each) for embedding.
- **Embedding Generation:** Generate semantic embeddings for each chunk using Azure OpenAI's embedding models.
- **Vector Storage in Azure SQL DB:** Store embeddings in Azure SQL DB using the new VECTOR data type for efficient similarity search.
- **Vector Search:** Query the database for the most relevant resume chunks based on a user query using built-in vector distance functions.
- **LLM Q&A:** Augment search results with GPT-4.1-based recommendations and summaries, grounded in the retrieved data.
- **Simplistic UI:** Interactive, step-by-step workflow with persistent results and clear progress indicators.

## Prerequisites
- **Azure Subscription** - Azure Free Trial subscription or Azure for Students subscription would also work
- **Python 3.8+**
- **Required Python packages** (see `requirements.txt`)
- **ODBC Driver 18+ for SQL Server** (for pyodbc)
- **Fabric Subscription** (Optional)

## Products & Services Used
- Azure SQL Database 
- Azure Document Intelligence (Form Recognizer)
- Azure OpenAI Service
- Streamlit
- Python (pandas, tiktoken, pyodbc, etc.)
- SQL Database on Fabric *(an alternative to Azure SQL Database)*

## Automated Deployments
- **ARM Template Scripts:**
    - ARM templates are provided separately to automate the deployment of required resources. Please refer to [this repository](https://github.com/Kushagra-2000/ARM_SQL_OpenAI) for scripts and detailed instructions. 
    - Follow the RAG for Unstructured Docs for this particular demo.
- **SQL on Fabric:**
    - Create a workspace in Fabric, if not existed before.
    - New Item > SQL Database (preview) > Provide DB name > Create

## Steps to Execute
1. **Clone the Repository**
2. **Install Requirements:**
   ```
   pip install -r requirements.txt
   ```
3. **Deploy Azure Resources:**
   - Use the provided ARM templates or Azure Portal to deploy SQL DB, Document Intelligence, and OpenAI resources.
   - Setup SQL on Fabric if using that as the database
4. **Setup Firewall Configuration:** (Skip this step if using SQL on Fabric)
   - Configure the firewall settings for the SQL server separately to allow access from your client IP addresses.
   - Go to the deployed SQL Server in the Azure Portal.
   - Navigate to Security > Networking > Virtual networks.
   - Add your client IP and click Save.
5. **Run the Streamlit App:**
   - Navigate to the cloned repository destination and then run the below command to start the app on `localhost:8501`
     ```
    streamlit run <filename.py> --server.maxUploadSize 500
     ```
6. **Configure Credentials:**
   - Launch the app and enter your Azure endpoints, API keys, and SQL connection string in the sidebar.
   - Credentials for Document Intelligence: Document Intelligence resource > Overview > Keys and endpoint
   - Credentials for OpenAI: OpenAI resource > Overview > Develop > Keys and endpoint
   - Connection String for Azure SQL DB: Azure SQL DB resource > Overview > Show database connection strings > ODBC > {Change Pwd parameter with your admin password set during deployment}
   - Connection String for SQL on Fabric: SQL DB > Settings > Connection Strings > ODBC > Copy string as it is > Authentication window would pop-up > Provide authentication details
7. **Talk to your docs:**
   - Upload [resume docs](https://www.kaggle.com/datasets/snehaanbhawal/resume-dataset) or upload your own docs and query upon them to see action of RAG in real-time

## Troubleshooting
- **Connection Errors:**
  - Ensure your SQL connection string is correct, and the ODBC driver is installed.
  - Verify API keys and endpoints for Azure services.
- **Table Creation Issues:**
  - Confirm your user has permission to create tables in the target database.
  - If using database for the first time or it is in Paused state, try creating table again after the DB is Running state - it would take 1-2 mins for DB to be ready, if in paused state.
- **Performance:**
  - Large PDFs or many files may take time to process and embed. Monitor resource usage.
- **Streamlit UI Issues:**
  - Refresh the page or restart the app if UI elements do not update as expected.

## Resources
- [Azure SQL DB Vector Support](https://devblogs.microsoft.com/azure-sql/eap-for-vector-support-refresh-introducing-vector-type/)
- [Azure Document Intelligence](https://learn.microsoft.com/azure/ai-services/document-intelligence/)
- [Azure OpenAI Service](https://learn.microsoft.com/azure/ai-services/openai/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [Project GitHub Repository](https://github.com/Azure-Samples/azure-sql-db-vector-search/tree/main/RAG-with-Documents)

---
