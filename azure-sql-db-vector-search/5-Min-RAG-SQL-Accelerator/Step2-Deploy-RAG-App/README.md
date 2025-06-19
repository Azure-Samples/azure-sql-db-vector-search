# SQL-Vector-Search Solution Accelerator

## Objective

This repository showcases two Streamlit applications that demonstrate how to build Retrieval-Augmented Generation (RAG) solutions using Azure SQL Database's native vector capabilities and Azure OpenAI. The apps are designed for:
- **Product Review Search**: Upload and semantically search product reviews using CSV data.
- **Resume Matching**: Upload and semantically match resumes using PDF documents.

Both apps allow users to generate embeddings, store/query them in Azure SQL DB, and perform LLM-powered Q&A for intelligent retrieval and recommendations.  
These demo follow the Jupyter notebook provided in the [azure-sql-db-vector-search repo](https://github.com/Azure-Samples/azure-sql-db-vector-search/tree/main) under the Azure-Samples GitHub repo. 

---

## Products & Services Used

- Azure SQL Database (VECTOR data type)
- Azure OpenAI Service
- Azure Document Intelligence (for resume parsing)
- SQL on Fabric *(alternative to Azure SQL DB)*
- Streamlit
- Python (pandas, pyodbc, tiktoken, etc.)

---

## Resources Deployment

### One Click Deployment
Automated deployment scripts are available in a separate [GitHub repository](https://github.com/Kushagra-2000/ARM_SQL_OpenAI) that will help to deploy required component.

This includes ARM templates to provision:
- Azure SQL DB
- Azure OpenAI
- Azure Document Intelligence (for resume app)

### Steps to Deploy SQL DB on Fabric
- Create a workspace in Fabric, if not existed before.
- New Item > SQL Database (preview) > Provide DB name > Create

---

## Run the Application

1. **Clone the Repository**
2. **Navigate** to corresponding repository depending upon structured or unstructured dataset.
3. **Install Requirements:**
   ```
   pip install -r requirements.txt
   ```
4. **Deploy Azure Resources:**
   - Use the provided ARM templates or Azure Portal to deploy SQL DB, Document Intelligence, and OpenAI resources.
   - Setup SQL on Fabric if using that as the database
5. **Setup Firewall Configuration:** (Skip this step if using SQL on Fabric)
   - Configure the firewall settings for the SQL server separately to allow access from your client IP addresses.
   - Go to the deployed SQL Server in the Azure Portal.
   - Navigate to Security > Networking > Virtual networks.
   - Add your client IP and click Save.
6. **Run the Streamlit App:**
   - Navigate to the cloned repository destination and then run the below command to start the app on `localhost:8501`
     ```
     streamlit run <filename.py> --server.maxUploadSize 500
     ```
7. **Configure Credentials:**
   - Launch the app and enter your Azure endpoints, API keys, and SQL connection string in the sidebar.
   - Credentials for Document Intelligence: Document Intelligence resource > Overview > Keys and endpoint
   - Credentials for OpenAI: OpenAI resource > Overview > Develop > Keys and endpoint
   - Connection String for Azure SQL DB: Azure SQL DB resource > Overview > Show database connection strings > ODBC > {Change Pwd parameter with your admin password set during deployment}
   - Connection String for SQL on Fabric: SQL DB > Settings > Connection Strings > ODBC > Copy string as it is > Authentication window would pop-up > Provide authentication details

---

## Deploy the App on Azure App Services

To deploy a Streamlit application on Azure App Service, follow these steps:  
1. Create an Azure App Service with B1 SKU or higher, as the free version does not support Streamlit.
2. Choose Python v3.10 or above for Streamlit in the App Service.
3. Choose Linux as the operating system for the App Service.
4. Make sure your code folder has a `requirements.txt` file with all the dependencies.
5. Add two files, `streamlit.sh` and `.deployment`, to the root directory of your project.
   - streamlit.sh
     ```
     pip install -r requirements.txt  
     python -m streamlit run app.py --server.port 8000 --server.address 0.0.0.0  
     ```
   - .deployment
     ```
     [config]  
     SCM_DO_BUILD_DURING_DEPLOYMENT=false
     ```
   - Replace `app.py` with your application name.
   - Use port 8000 because Azure App Service by default exposes only 8000 and 443 ports.  
6. Open Visual Studio Code and install the Azure Extension Pack.
7. Log in to Visual Studio Code with your Azure account.
8. Use the `Azure App Service: Deploy to Web App` command in Visual Studio Code and select your App Service name.
9. Wait for deployment to be finished.
10. Go to the Azure portal and update the `Startup Command` configuration for the App Service and set the value to `bash /home/site/wwwroot/streamlit.sh`.
    - You can find this configuration inside `App Service > Settings > Configurations > General settings`.
11. Wait for some seconds and visit the application URL. Congratulations! You have successfully deployed your Streamlit application to the Azure App Service.

Refer to following resources for any further clarification:
- [Learn Microsoft | Answers](https://learn.microsoft.com/en-us/answers/questions/1470782/how-to-deploy-a-streamlit-application-on-azure-app#:~:text=Deploying%20Streamlit%20Application%20on%20Azure%20App%20Service)
- [Tech Community Microsoft](https://techcommunity.microsoft.com/blog/appsonazureblog/deploy-streamlit-on-azure-web-app/4276108)


---

## What Next?

Once you've successfully deployed and explored the Streamlit applications, here are some next steps to deepen your understanding and expand your solution:

- **Explore the Jupyter Notebook Project**: Visit the companion GitHub repository that includes Jupyter notebooks to:
  - Understand the underlying code and logic behind embedding generation, vector storage, and querying.
  - Experiment with different datasets and prompts.
  - Learn how to customize the pipeline for your own use case.
  - Checkout implementation using Semantic Kernel or LangChain.

- **Dive into Azure Portal**:
  - Monitor and manage your deployed resources.
  - Explore Azure SQL DB’s vector capabilities and performance tuning.
  - Review usage metrics and cost estimations.

- **Customize the Apps**: Modify the Streamlit apps to:
  - Add new data sources (e.g., JSON, web scraping).
  - Enhance the UI/UX for specific business scenarios.
    
- **Build Your Own Use Case**:
  - Use Azure SQL DB or SQL on Fabric as your vector store.
  - Design a RAG solution tailored to your domain—be it legal, healthcare, customer support, or internal knowledge bases.
  - Share your solution with the community.

---

## Troubleshooting
- **Connection Errors:**
  - Ensure your SQL connection string is correct and the ODBC driver is installed.
  - Verify API keys and endpoints for Azure services.
- **Table Creation Issues:**
  - Confirm your user has permissions to create tables in the target database.
  - If using the database for the first time or it is in Paused state, try creating table again after the database is in Running state - it would take 1-2 mins for DB to be ready, if in paused state.
- **Embedding/Vector Errors:**
  - Use the correct double-casting in SQL queries as shown in the app.
- **Performance:**
  - Large PDFs or many files may take time to process and embed. Monitor resource usage.
- **Streamlit UI Issues:**
  - Refresh the page or restart the app if UI elements do not update as expected.

---

## 📚 Resources

- [Azure SQL DB Vector Support](https://devblogs.microsoft.com/azure-sql/eap-for-vector-support-refresh-introducing-vector-type/)
- [Azure Document Intelligence](https://learn.microsoft.com/azure/ai-services/document-intelligence/)
- [Azure OpenAI Service](https://learn.microsoft.com/azure/ai-services/openai/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [Project GitHub Repository](https://github.com/Azure-Samples/azure-sql-db-vector-search/tree/main/RAG-with-Documents)

---
