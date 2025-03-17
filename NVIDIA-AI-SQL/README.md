# RAG with NVIDIA AI and Azure SQL

This Jupyter Notebook implements **Retrieval-Augmented Generation (RAG)** using **NVIDIA AI** models for embeddings and chat, and **Azure SQL Database** for storing and retrieving resume embeddings.

## Features
- Uses **NVIDIA AI models** (`meta/llama-3.3-70b-instruct` and `nvidia/embed-qa-4`).
- Stores resume embeddings in **Azure SQL Database**.
- Supports **optimized vector search** for relevant candidates.
- Implements **streaming responses** for better chatbot experience.

## Setup Instructions
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Set up your `.env` file with API keys:
   ```bash
   NVIDIA_API_KEY=your_nvidia_api_key_here
   NVIDIA_CHAT_API_KEY=your_nvidia_chat_model_api_key_here
   AZUREDOCINTELLIGENCE_ENDPOINT=your_azure_doc_intelligence_endpoint_here   AZUREDOCINTELLIGENCE_API_KEY=your_azure_doc_intelligence_api_key_here
   AZURE_SQL_CONNECTION_STRING=your_azure_sql_connection_string_here
   FILE_PATH=Path to the resume dataset
   ```
3. Run the notebook.

## File Structure
- `NVIDIA-RAG-with-resumes.ipynb` → Main Jupyter Notebook
- `.env` → Environment variables for API keys
- `README.md` → Documentation
- `CreateTable.sql` → Create Table for Azure SQL Database

## Dataset

We use a sample dataset from [Kaggle](https://www.kaggle.com/datasets/snehaanbhawal/resume-dataset) containing PDF resumes for this tutorial. For the purpose of this tutorial we will use 120 resumes from the **Information-Technology** folder



