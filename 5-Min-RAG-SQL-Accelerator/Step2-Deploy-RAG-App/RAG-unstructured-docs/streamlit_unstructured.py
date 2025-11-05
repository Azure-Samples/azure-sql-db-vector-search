import streamlit as st
import os
import re
import pandas as pd
import tiktoken
import requests
import numpy as np
import json
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI
import pyodbc
import struct
from azure.identity import DefaultAzureCredential
from azure.identity import InteractiveBrowserCredential

# Adjust the layout to make the main window wide
st.set_page_config(layout="wide", page_title="RAG with Azure SQL and OpenAI")

# Custom CSS to style the Streamlit app
st.markdown(
    """
    <style>
    .main {
        overflow-y: auto !important;
    }
    [data-testid="stExpander"] {
        background-color: #f4f1ff;
        border-radius: 5px;
        color: #000;
    }
    /* Remove any overflow: hidden or similar rules that could break scrolling */
    </style>
    """,
    unsafe_allow_html=True
)

# --- Streamlit Sidebar for Configuration ---
with st.sidebar:
    st.subheader('🔒 Configuration Strings (Session Only)')
    st.markdown('Enter your Azure SQL / DocIntelligence / OpenAI credentials. These are only stored for this session and never saved.')
    SQL_CONNECTION_STRING = st.text_input('SQL Connection String', placeholder="Enter your Azure SQL connection string", type='default', key='sql_conn', 
                                          help="ODBC Connection string needs to be used. Do update the password parameter in the string with your password.")
    ENTRA_CONNECTION_STRING = st.text_input("Azure Entra ID Connection String (Optional)", placeholder="Enter your Entra ID connection string", key="entra_connection_string")
    AZUREDOCINTELLIGENCE_ENDPOINT = st.text_input('Azure Document Intelligence Endpoint', type='default', key='docint_endpoint')
    AZUREDOCINTELLIGENCE_API_KEY = st.text_input('Azure Document Intelligence API Key', type='password', key='docint_key')
    AZOPENAI_ENDPOINT = st.text_input('Azure OpenAI Endpoint', type='default', key='openai_endpoint')
    AZOPENAI_API_KEY = st.text_input('Azure OpenAI API Key', type='password', key='openai_key') 
    st.text_input("Embedding Model Deployment Name", value="text-embedding-ada-002", key="embedding_model")
    st.text_input("Chat Completion Model Name", value="gpt-4.1", key="gpt-4.1")


# Store config in session state for use throughout the app
st.session_state['AZUREDOCINTELLIGENCE_ENDPOINT'] = AZUREDOCINTELLIGENCE_ENDPOINT
st.session_state['AZUREDOCINTELLIGENCE_API_KEY'] = AZUREDOCINTELLIGENCE_API_KEY
st.session_state['AZOPENAI_ENDPOINT'] = AZOPENAI_ENDPOINT
st.session_state['AZOPENAI_API_KEY'] = AZOPENAI_API_KEY
st.session_state['SQL_CONNECTION_STRING'] = SQL_CONNECTION_STRING
st.session_state['ENTRA_CONNECTION_STRING'] = ENTRA_CONNECTION_STRING

# Helper to get config from session state
get_config = lambda k: st.session_state.get(k, '')

# Azure Document Intelligence setup
def get_document_analysis_client():
    endpoint = get_config('AZUREDOCINTELLIGENCE_ENDPOINT')
    key = get_config('AZUREDOCINTELLIGENCE_API_KEY')
    return DocumentAnalysisClient(endpoint=endpoint, credential=AzureKeyCredential(key))

# Azure OpenAI setup
def get_openai_embedding_url():
    endpoint = get_config('AZOPENAI_ENDPOINT')
    deployment = "text-embedding-ada-002"
    return f"{endpoint}openai/deployments/{deployment}/embeddings?api-version=2023-05-15"

def get_openai_key():
    return get_config('AZOPENAI_API_KEY')

# SQL DB connection helper
def get_mssql_connection():
    sql_connection_string = get_config('SQL_CONNECTION_STRING')
    entra_connection_string = get_config('ENTRA_CONNECTION_STRING')

    if entra_connection_string:
        credential = InteractiveBrowserCredential()
        # credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
        token = credential.get_token('https://database.windows.net/.default')
        token_bytes = token.token.encode('UTF-16LE')
        token_struct = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)
        SQL_COPT_SS_ACCESS_TOKEN = 1256
        conn = pyodbc.connect(entra_connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
    elif sql_connection_string:
        conn = pyodbc.connect(sql_connection_string)
    else:
        raise ValueError("No valid connection string found.")
    
    return conn

# PDF extraction
def extract_text_from_pdf(pdf_file):
    document_analysis_client = get_document_analysis_client()
    poller = document_analysis_client.begin_analyze_document("prebuilt-layout", document=pdf_file)
    result = poller.result()
    text = ""
    for page in result.pages:
        for line in page.lines:
            text += line.content + " "
    return text

def clean_text(text):
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    return text

# Function to split text into chunks of 500 tokens
def split_text_into_token_chunks(text, max_tokens=500):
    tokenizer = tiktoken.get_encoding("cl100k_base")
    tokens = tokenizer.encode(text)
    chunks = []
    for i in range(0, len(tokens), max_tokens):
        chunk_tokens = tokens[i:i + max_tokens]
        chunk_text = tokenizer.decode(chunk_tokens)
        chunks.append(chunk_text)
    return chunks

# Embedding generation
def get_embedding(text):
    openai_url = get_openai_embedding_url()
    openai_key = get_openai_key()
    response = requests.post(openai_url,
        headers={"api-key": openai_key, "Content-Type": "application/json"},
        json={"input": [text]}
    )
    if response.status_code == 200:
        response_json = response.json()
        embedding = json.loads(str(response_json['data'][0]['embedding']))
        return embedding
    else:
        return None

# Insert into SQL DB
def insert_embeddings_to_db(df):
    """
    Insert the embeddings DataFrame into the resumedocs table using the correct VECTOR type handling.
    """
    conn = get_mssql_connection()
    cursor = conn.cursor()
    cursor.fast_executemany = True
    errors = []
    rows_inserted = 0
    for index, row in df.iterrows():
        chunkid = row['chunkid']
        filename = row['filename']
        chunk = row['chunk']
        embedding = row['embedding']
        embedding_json = json.dumps(embedding)
        try:
            # Use NVARCHAR(MAX) to avoid truncation for large embeddings
            query = """
            INSERT INTO resumedocs (chunkid, filename, chunk, embedding)
            VALUES (?, ?, ?, CAST(CAST(? AS NVARCHAR(MAX)) AS VECTOR(1536)))
            """
            cursor.execute(query, chunkid, filename, chunk, embedding_json)
            rows_inserted += 1
        except Exception as e:
            errors.append(f"Row {index}: {e}")
    conn.commit()
    conn.close()
    if errors:
        st.error(f"Some rows failed to insert: {errors}")
    elif rows_inserted == 0:
        st.warning("No rows were inserted into the table. Please check your data and table schema.")
    else:
        st.success(f"{rows_inserted} rows inserted successfully into the table.")

# Vector search
def vector_search_sql(query, num_results=5):
    """
    Perform a vector similarity search in the resumedocs table using the VECTOR_DISTANCE function.
    """
    conn = get_mssql_connection()
    cursor = conn.cursor()
    user_query_embedding = get_embedding(query)
    embedding_json = json.dumps(user_query_embedding)
    sql_similarity_search = """
    SELECT TOP (?) filename, chunkid, chunk,
           1-vector_distance('cosine', CAST(CAST(? AS NVARCHAR(MAX)) AS VECTOR(1536)), embedding) AS similarity_score,
           vector_distance('cosine', CAST(CAST(? AS NVARCHAR(MAX)) AS VECTOR(1536)), embedding) AS distance_score
    FROM dbo.resumedocs
    ORDER BY distance_score
    """
    cursor.execute(sql_similarity_search, num_results, embedding_json, embedding_json)
    results = cursor.fetchall()
    conn.close()
    return results

# LLM completion
def generate_completion(search_results, user_input):
    api_key = get_openai_key()
    azure_endpoint = get_config('AZOPENAI_ENDPOINT')
    chat_model = "gpt-4.1"
    client = AzureOpenAI(
        api_key=api_key,
        api_version="2023-05-15",
        azure_endpoint=azure_endpoint
    )
    system_prompt = '''
You are an intelligent & funny assistant who will exclusively answer based on the data provided in the `search_results`:
- Use the information from `search_results` to generate your top 3 responses. If the data is not a perfect match for the user's query, use your best judgment to provide helpful suggestions and include the following format:
  File: {filename}
  Chunk ID: {chunkid}
  Similarity Score: {similarity_score}
  Add a small snippet from the Relevant Text: {chunktext}
  Do not use the entire chunk
- Avoid any other external data sources.
- Add a summary about why the candidate maybe a goodfit even if exact skills and the role being hired for are not matching , at the end of the recommendations. Ensure you call out which skills match the description and which ones are missing. If the candidate doesnt have prior experience for the hiring role which we may need to pay extra attention to during the interview process.
- Add a Microsoft related interesting fact about the technology that was searched 
'''
    messages = [{"role": "system", "content": system_prompt}]
    result_list = []
    for result in search_results:
        filename, chunkid, chunktext, similarity_score, _ = result
        result_list.append({
            "filename": filename,
            "chunkid": chunkid,
            "chunktext": chunktext,
            "similarity_score": similarity_score
        })
    messages.append({"role": "system", "content": f"{result_list}"})
    messages.append({"role": "user", "content": user_input})
    response = client.chat.completions.create(model=chat_model, messages=messages, temperature=0)
    return response.choices[0].message.content

# --- Table Creation Utility ---
def check_and_create_table():
    conn = get_mssql_connection()
    cursor = conn.cursor()
    # Check if table exists
    cursor.execute("""
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'resumedocs'
    """)
    exists = cursor.fetchone()[0]
    if not exists:
        # Create table using schema from CreateTable.sql
        cursor.execute('''
            CREATE TABLE resumedocs (
                id INT IDENTITY(1,1) PRIMARY KEY,
                chunkid NVARCHAR(255),
                filename NVARCHAR(255),
                chunk NVARCHAR(MAX),
                embedding VECTOR(1536)
            )
        ''')
        conn.commit()
        conn.close()
        return False  # Table was created
    conn.close()
    return True  # Table already existed

# Streamlit UI
st.title("RAG Resume Matcher with Azure SQL DB, Document Intelligence, and OpenAI")
st.markdown("In this tutorial we will be using [PDF resumes from Kaggle](https://www.kaggle.com/datasets/snehaanbhawal/resume-dataset), " \
"extract and chunk its text, generate its embeddings, store/query in Azure SQL DB, and perform Q&A using LLM.  \nFor detailed explanation, " \
"please refer to the [GitHub repo](https://github.com/Azure-Samples/azure-sql-db-vector-search/tree/main/RAG-with-Documents).")
st.markdown("""**Note:** This is a demo app. Please do not use it for production purposes.  
            Do check for the Firewall setup in your Azure SQL Database. You can use the [Azure Portal](https://portal.azure.com/) to configure the firewall settings to allow access from your IP address. 
            Steps to configure the firewall can be found [here](https://github.com/Kushagra-2000/sql-vector-search-demo/blob/main/README.md#:~:text=Setup%20Firewall%20Configuration).
            """)

# Step 1: Check/Create Table
st.subheader("Step 1: SQL Database Table Creation")
with st.expander("**Table Creation Process**"):
    st.markdown("We will insert our vectors into the SQL Table. Azure SQL DB now has a dedicated, native, data type for storing vectors: the `vector` data type. Read about the preview [here](https://devblogs.microsoft.com/azure-sql/eap-for-vector-support-refresh-introducing-vector-type/).  " \
    "\nTo facilitate creation of the table, following SQL query would be executed:")
    st.code("""
    IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'resumedocs')
    BEGIN
        CREATE TABLE resumedocs (
            id INT IDENTITY(1,1) PRIMARY KEY,
            chunkid NVARCHAR(255),
            filename NVARCHAR(255),
            chunk NVARCHAR(MAX),
            'embedding VECTOR(1536)'
        )
    END
    """)
if st.button("Check/Create documents Table"):
    existed = check_and_create_table()
    if existed:
        st.success("Table already exists in the database.")
    else:
        st.success("Table was created in the database.")

# Step 2: Upload PDF files
st.subheader("Step 2: Process PDF documents")
with st.expander("**Dataset Processing**"):
    st.markdown("Next we'll be using **Azure Document Intelligence** to analyze text and structured data from the PDF resumes. " \
    "DocumentAnalysisClient provides operations for analyzing input documents using prebuilt and custom models through the `begin_analyze_document` and `begin_analyze_document_from_url` APIs. In this tutorial, we are using the [prebuilt-layout](https://learn.microsoft.com/en-us/python/api/overview/azure/ai-formrecognizer-readme?view=azure-python#using-prebuilt-models)." )
    st.markdown("When faced with content that exceeds the embedding limit, we usually also chunk the content into smaller pieces and then embed those one at a time. " \
    "Here we will use `tiktoken` to chunk the extracted text into **token sizes of 500**, as we will later pass the extracted chunks to to the `text-embedding-small` model "
    "for [generating text embeddings](https://learn.microsoft.com/en-us/azure/ai-services/openai/tutorials/embeddings?tabs=python-new%2Ccommand-line&pivots=programming-language-python) as this has a model input token limit of 8192.")
uploaded_files = st.file_uploader("Upload docs", type=["pdf"], accept_multiple_files=True)

# Use session state to avoid reprocessing and persist results
if 'df' not in st.session_state:
    st.session_state['df'] = None
if 'result_df' not in st.session_state:
    st.session_state['result_df'] = None
if 'insert_status' not in st.session_state:
    st.session_state['insert_status'] = None

if uploaded_files:
    if st.session_state.get('last_uploaded_files') != [f.name for f in uploaded_files]:
        # Only process if new files are uploaded
        all_data = []
        status_placeholder = st.empty()  # Placeholder for status messages
        total_chunks = 0
        for file in uploaded_files:
            status_placeholder.info(f"Processing: {file.name}")
            text = extract_text_from_pdf(file)
            cleaned = clean_text(text)
            chunks = split_text_into_token_chunks(cleaned)
            total_chunks += len(chunks)
            status_placeholder.success(f"Extracted {len(chunks)} chunks from {file.name}")
            for chunk_id, chunk in enumerate(chunks):
                chunk_text = chunk.strip() if chunk.strip() else "NULL"
                unique_chunk_id = f"{file.name}_{chunk_id}"
                all_data.append({
                    "file_name": file.name,
                    "chunk_id": chunk_id,
                    "chunk_text": chunk_text,
                    "unique_chunk_id": unique_chunk_id
                })
        df = pd.DataFrame(all_data)
        st.session_state['df'] = df
        st.session_state['result_df'] = None  # Reset embeddings if new files
        st.session_state['insert_status'] = None
        st.session_state['last_uploaded_files'] = [f.name for f in uploaded_files]
        # After processing all files, show a summary success message
        status_placeholder.success(f"Processed {len(uploaded_files)} file(s) and extracted a total of {total_chunks} text chunks.")
    else:
        df = st.session_state['df']
    st.write("Preview of processed dataset:")
    st.dataframe(df.head(6), height=250)

# Step 3: Generate embeddings
st.subheader("Step 3: Embedding Generation")
with st.expander("**What are Embeddings ?**"):
    st.markdown("""
                - After extracting and chunking the text from PDF resumes, we will generate embeddings for each chunk. These embeddings are **numerical representations** of the text that capture its semantic meaning. 
                By creating embeddings for the text chunks, we can perform advanced similarity searches and enhance language model generation. 
                - We will use the Azure OpenAI API to generate these embeddings. The `get_embedding` function defined below takes a piece of text as input 
                and returns its embedding using the `text-embedding-ada-002` model
                """)

if st.session_state['df'] is not None:
    if st.button("Generate Embeddings") or st.session_state.get('result_df') is not None:
        if st.session_state.get('result_df') is None:
            df = st.session_state['df']
            all_filenames, all_chunkids, all_chunks, all_embeddings = [], [], [], []
            for index, row in df.iterrows():
                filename = row['file_name']
                chunkid = row['unique_chunk_id']
                chunk = row['chunk_text']
                embedding = get_embedding(chunk)
                if embedding is not None:
                    all_filenames.append(filename)
                    all_chunkids.append(chunkid)
                    all_chunks.append(chunk)
                    all_embeddings.append(embedding)
                if (index + 1) % 10 == 0:
                    st.write(f"Completed {index + 1} rows")
            # Always show the final count
            st.success(f"Completed {len(df)} rows")
            result_df = pd.DataFrame({
                'filename': all_filenames,
                'chunkid': all_chunkids,
                'chunk': all_chunks,
                'embedding': all_embeddings
            })
            st.session_state['result_df'] = result_df
        st.dataframe(st.session_state['result_df'].head())

# Step 4: Insert into DB
st.subheader("Step 4: Insert data into SQL DB")
with st.expander("**Vector Embedding Storage in Azure SQL Database**"):
    st.markdown("""
    We will insert our vectors into the SQL Table now. The table embeddings has a column called **vector** which is vector(1536) type.

    We will pass the vectors by converting a JSON array to a compact **binary** representation of a vector. Vectors are stored in an efficient binary format that also enables usage of dedicated CPU vector processing extensions like SIMD and AVX.       
    """)
    # st.code("""
    #         INSERT INTO resumedocs (chunkid, filename, chunk, embedding)
    #         VALUES (?, ?, ?, CAST(CAST(? AS NVARCHAR(MAX)) AS VECTOR(1536)))
    #         """)
if st.session_state.get('result_df') is not None:
    if st.button("Insert Embeddings into Azure SQL DB") or st.session_state.get('insert_status') is not None:
        if st.session_state.get('insert_status') is None:
            result_df = st.session_state['result_df']
            insert_embeddings_to_db(result_df)
            st.session_state['insert_status'] = True
        with st.expander("**Preview of the inserted data:**"):
            st.dataframe(st.session_state['result_df'].head())

# Step 5: Query and Q&A
st.subheader("Step 5: Vector Search and LLM Q&A")
with st.expander("**Vector Search**"):
    st.markdown(""" 
Let's now query our ResumeDocs table to get the top similar candidates given the User search query.

What we are doing: Given any user search query, we can get the vector representation of that text.

Then we can use that vector to calculate the **cosine distance** against all the resume embeddings stored in the database and take only the closest ones which will return the resumes most relevant to the user's query. This helps in finding the most suitable candidates based on their resumes.
                
**SQL Query:**
                """)
    st.code("""
            SELECT TOP (?) filename, chunkid, chunk,
           VECTOR_DISTANCE('cosine', @e, Vector) AS distance_score,
    FROM dbo.resumedocs
    ORDER BY distance_score
    """)

with st.expander("**Augment LLM Generation**"):
    st.markdown("""
    A helper function is created to feed prompts into the **OpenAI Completions model** & create interactive loop where you can pose questions to the model and receive information grounded in your data.

The function `generate_completion` is defined to help ground the GPT 4.1 model with prompts and system instructions. 
We are passing the results of the `vector_search_sql` function to the model and we define the system prompt as follows:
                """)
    st.code("""
            '''You are an intelligent & funny assistant who will exclusively answer based on the data provided in the `search_results`:
- Use the information from `search_results` to generate your top 3 responses. If the data is not a perfect match for the user's query, use your best judgment to provide helpful suggestions and include the following format:
  File: {filename}
  Chunk ID: {chunkid}
  Similarity Score: {similarity_score}
  Add a small snippet from the Relevant Text: {chunktext}
  Do not use the entire chunk
- Avoid any other external data sources.
- Add a summary about why the candidate maybe a goodfit even if exact skills and the role being hired for are not matching , at the end of the recommendations. Ensure you call out which skills match the description and which ones are missing. If the candidate doesnt have prior experience for the hiring role which we may need to pay extra attention to during the interview process.
- Add a Microsoft related interesting fact about the technology that was searched'''
            """)


user_query = st.text_input("What role or skills are you hiring for?")

# Use session state to persist results
if 'search_results' not in st.session_state:
    st.session_state['search_results'] = None
if 'llm_response' not in st.session_state:
    st.session_state['llm_response'] = None

if st.button("**Find Candidates**") and user_query:
    search_results = vector_search_sql(user_query)
    st.session_state['search_results'] = search_results
    st.session_state['llm_response'] = None  # Reset LLM response on new search

if st.session_state['search_results']:
    st.write("**Top matching candidates:**")
    for r in st.session_state['search_results']:
        st.write(f"File: {r[0]}, Similarity Score: {r[3]:.3f}, Chunk ID: {r[1]}")
        with st.expander(f"**Chunk Snippet:** {r[2][:50]}..."):
            st.write(r[2])
    st.write("---")
    if st.button("**Ask LLM for Recommendation**"):
        completions_results = generate_completion(st.session_state['search_results'], user_query)
        st.session_state['llm_response'] = completions_results

if st.session_state['llm_response']:
    st.write(st.session_state['llm_response'])
