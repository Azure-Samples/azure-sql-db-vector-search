import streamlit as st
import os
import pandas as pd
import json
import requests
from dotenv import load_dotenv
from openai import AzureOpenAI
import pyodbc
from azure.identity import DefaultAzureCredential
import struct

# Adjust the layout to make the main window wide
st.set_page_config(layout="wide", page_title="RAG with Azure SQL and OpenAI")

# Load environment variables
load_dotenv()

# Update custom CSS for styling expander elements
st.markdown(
    """
    <style>
    [data-testid="stExpander"] {
        background-color: #f4f1ff; 
        border-radius: 5px;
        color: #000;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Move configuration requirements to a collapsible sidebar
with st.sidebar:
    st.header("Configuration Requirements")
    st.text_input("Azure SQL Database Connection String", placeholder="Enter your SQL connection string", key="sql_connection_string", 
                  help="ODBC Connection string needs to be used. Do update the password parameter in the string with your password.")
    st.text_input("Azure Entra ID Connection String (Optional)", placeholder="Enter your Entra ID connection string", key="entra_connection_string")
    st.text_input("Azure OpenAI Endpoint", placeholder="https://<your-resource-name>.openai.azure.com/", key="openai_endpoint")
    st.text_input("Azure OpenAI API Key", type="password", key="openai_api_key")
    st.text_input("Embedding Model Deployment Name", placeholder="text-embedding-3-small", key="embedding_model")
    st.text_input("Chat Completion Model Name", placeholder="gpt-4.1", key="gpt-4.1")

# Automatically expand the sidebar when the user visits the site
st.sidebar.markdown("<style>.sidebar .sidebar-content {width: 300px;}</style>", unsafe_allow_html=True)

# Streamlit App Title
st.title("Retrieval-Augmented Generation with Azure SQL and OpenAI")

# Add a subheader below the title with dataset information and link
st.write("In this tutorial we will be using the [Fine Foods Review Dataset](https://www.kaggle.com/datasets/pookam90/fine-food-reviews-with-embeddings?resource=download), " \
"process it in dataframe, generate its embeddings, store/query in Azure SQL DB, and perform Q&A using LLM. For detailed explanation, " \
"please refer to the [GitHub repo](https://github.com/Azure-Samples/azure-sql-db-vector-search/tree/main/Retrieval-Augmented-Generation).")
st.markdown("**Note:** This is a demo app. Please do not use it for production purposes. The credentials are stored in session state and are not secure. ")

# Section: User Inputs for Configuration
# Use the provided values directly in the session without storing them permanently
if st.session_state.sql_connection_string:
    os.environ['SQL_CONNECTION_STRING'] = st.session_state.sql_connection_string
if st.session_state.entra_connection_string:
    os.environ['ENTRAID_CONNECTION_STRING'] = st.session_state.entra_connection_string
if st.session_state.openai_endpoint:
    os.environ['AZURE_OPENAI_ENDPOINT'] = st.session_state.openai_endpoint
if st.session_state.openai_api_key:
    os.environ['AZURE_OPENAI_API_KEY'] = st.session_state.openai_api_key
if st.session_state.embedding_model:
    os.environ['AZURE_OPENAI_EMBEDDING_MODEL_DEPLOYMENT_NAME'] = st.session_state.embedding_model



def get_mssql_connection():
    """
    Establish a connection to Azure SQL Database.
    """
    entra_connection_string = os.getenv('ENTRAID_CONNECTION_STRING')
    sql_connection_string = os.getenv('SQL_CONNECTION_STRING')

    if entra_connection_string:
        credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
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


# Section 1: Check and Create Table in Azure SQL Database
st.subheader("Step 1: Create Table in Azure SQL Database")

# Add collapsible markdown section to explain the table creation process
with st.expander("**Table Creation Process**"):
    st.markdown("We will insert our vectors into the SQL Table. Azure SQL DB now has a dedicated, native, data type for storing vectors: the vector data type. Read about the preview [here](https://devblogs.microsoft.com/azure-sql/eap-for-vector-support-refresh-introducing-vector-type/).  " \
    "\nTo facilitate creation of the table, following SQL query would be executed:")
    st.code("""
    IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'embeddings')
    BEGIN
        CREATE TABLE [dbo].[embeddings]
        (
            [Id] [bigint] NULL,
            [ProductId] [nvarchar](500) NULL,
            [UserId] [nvarchar](50) NULL,
            [Score] [bigint] NULL,
            [Summary] [nvarchar](max) NULL,
            [Text] [nvarchar](max) NULL,
            [Combined] [nvarchar](max) NULL,
            '[Vector] [vector](1536) NULL'
        )
    END
    """)

def check_and_create_table():
    conn = get_mssql_connection()
    cursor = conn.cursor()
    
    # Check if the table exists
    check_table_query = """
    IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'embeddings')
    BEGIN
        CREATE TABLE [dbo].[embeddings]
        (
            [Id] [bigint] NULL,
            [ProductId] [nvarchar](500) NULL,
            [UserId] [nvarchar](50) NULL,
            [Score] [bigint] NULL,
            [Summary] [nvarchar](max) NULL,
            [Text] [nvarchar](max) NULL,
            [Combined] [nvarchar](max) NULL,
            [Vector] [vector](1536) NULL
        )
    END
    """
    cursor.execute(check_table_query)
    conn.commit()
    conn.close()

if st.button("Create Table"):
    try:
        check_and_create_table()
        st.success("Table checked and created successfully in Azure SQL Database!")
    except Exception as e:
        st.error(f"An error occurred: {e}")



# Section 2: Upload and Process Dataset
st.subheader("Step 2: Upload and Process Dataset")

with st.expander("**About Dataset**"):
    st.markdown("The dataset is about the customer reviews dataset from FineFoods and enriching it with embeddings generated via the `text-embedding-3-small` Azure OpenAI model. " \
    "The embeddings will be generated using the concatenation of `Summary + Text` field. Imagine a user asks, “What's the best coffee?” We'll transform their query into a vector and search our database of reviews to extract all products that are similar to provided question.")
    st.markdown("You can find the sample dataset here: [GitHub](https://github.com/Azure-Samples/azure-sql-db-vector-search/blob/main/Datasets). Check out the **reviews.csv** file for this step. ")

with st.expander("**Dataset Processing**"):
    st.markdown("Next we'll perform some light data cleaning on the uploaded reviews dataset by removing redundant whitespace and cleaning up the punctuation to prepare the data for tokenization." \
    " We will also remove comments that are too long for the token limit (8192 tokens - the maximum length of input text for the Azure OpenAI embedding models). When faced with content that exceeds the embedding limit, you can also chunk the content into smaller pieces and then embed those one at a time. You can read more about data chunking [here](https://learn.microsoft.com/en-us/azure/search/vector-search-how-to-chunk-documents)")

uploaded_file = st.file_uploader("Upload the CSV file for embedding generation", type="csv")
if uploaded_file is not None:
    # Only reload DataFrame if file changes
    if 'uploaded_df' not in st.session_state or st.session_state.get('last_uploaded_file') != uploaded_file.name:
        df = pd.read_csv(uploaded_file)
        required_columns = ["Id", "Time", "ProductId", "UserId", "Score", "Summary", "Text"]
        df = df[required_columns]
        df["combined"] = df["Summary"].str.strip() + ": " + df["Text"].str.strip()
        st.session_state['uploaded_df'] = df
        st.session_state['last_uploaded_file'] = uploaded_file.name
        st.session_state['embeddings_df'] = None  # Reset embeddings if new file
        st.session_state['search_results'] = None
    else:
        df = st.session_state['uploaded_df']
    st.write("Preview of Uploaded Dataset:")
    st.dataframe(df.head())
    st.write("Processed Dataset:")
    st.dataframe(df.head())

# Section 3: Generate and display Embeddings for the first 10 rows of the DataFrame
st.subheader("Step 3: Generate Embeddings")

with st.expander("**What are Embeddings ?**"):
    st.markdown("""
    An **embedding** is a special format of data representation that is optimized for use by machine learning models and algorithms. It is an information-dense representation of the semantic meaning of a piece of text.

    Each embedding is a vector of floating point numbers. The key characteristic of these vectors is that the distance between two embeddings in the vector space is indicative of the semantic similarity between the two corresponding inputs in their original format. For instance:

    - If two pieces of text are semantically similar, their vector representations will also be close to each other.
    - Conversely, dissimilar texts will have embeddings that are farther apart in the vector space.
                
    We will now generate the embeddings for the **combined** column (*Product summary + Review*) using the defined `get_embeddings` function that leverages the Azure OpenAI `text-embedding-3-small` model.
    Since the embedding generation process can be time-consuming, we will only generate embeddings for the *first 10 rows* of the dataset for demonstration purposes.
    """)

def get_embedding(text):
    """
    Get sentence embedding using the Azure OpenAI text-embedding-ada-002.
    """
    openai_url = os.environ.get('AZURE_OPENAI_ENDPOINT') + "/openai/deployments/text-embedding-ada-002/embeddings?api-version=2023-05-15"
    response = requests.post(
        openai_url,
        headers={"api-key": os.environ.get('AZURE_OPENAI_API_KEY'), "Content-Type": "application/json"},
        json={"input": [text]}
    )
    return response.json()['data'][0]['embedding']

def generate_embeddings(df):
    """
    Generate embeddings for the first 10 rows of the DataFrame.
    """
    df = df.head(10).copy()  
    df.loc[:, "vector"] = df["combined"].apply(get_embedding)  
    return df

if uploaded_file is not None:
    if st.button("Generate Embeddings") or st.session_state.get('embeddings_df') is not None:
        if st.session_state.get('embeddings_df') is None:
            df = st.session_state['uploaded_df']
            embeddings_df = generate_embeddings(df)
            st.session_state['embeddings_df'] = embeddings_df
        else:
            embeddings_df = st.session_state['embeddings_df']
        st.success("Embeddings generated successfully!")
        st.dataframe(embeddings_df.head(10))

# Section 4: Upload Pre-Generated Embeddings to Database
st.subheader("Step 4: Upload Pre-Generated Embeddings")

with st.expander("**Vector Embedding Storage in Azure SQL Database**"):
    st.markdown("""
    Let's import **finefoodembeddings.csv** ([GitHub](https://github.com/Azure-Samples/azure-sql-db-vector-search/blob/main/Datasets/FineFoodEmbeddings.csv) / [Kaggle](https://www.kaggle.com/datasets/pookam90/fine-food-reviews-with-embeddings?resource=download)) which contains embeddings for the entire dataset calculated in the same manner as above, directly to the SQL table      

    We will insert our vectors into the SQL Table now. The table embeddings has a column called **vector** which is vector(1536) type.

    We will pass the vectors by converting a JSON array to a compact **binary** representation of a vector. Vectors are stored in an efficient binary format that also enables usage of dedicated CPU vector processing extensions like SIMD and AVX.       
    """)


# Upload pre-generated embeddings CSV file
uploaded_embeddings_file = st.file_uploader("Upload the CSV file with pre-generated embeddings", type="csv")

if uploaded_embeddings_file is not None:
    embeddings_df = pd.read_csv(uploaded_embeddings_file)
    st.write("Preview of Uploaded Embeddings Dataset:")
    st.dataframe(embeddings_df.head())  # Keep preview small for performance

    # Ensure the vector column is properly deserialized into a list of numeric values
    embeddings_df['vector'] = embeddings_df['vector'].apply(json.loads)

    # ✅ Pre-serialize vectors once (avoid doing inside loop)
    embeddings_df['vector'] = embeddings_df['vector'].apply(json.dumps)

    # ✅ Prepare data as a list of tuples using zip (faster than iterrows)
    data_to_insert = list(zip(
        embeddings_df['Id'],
        embeddings_df['ProductId'],
        embeddings_df['UserId'],
        embeddings_df['Score'],
        embeddings_df['Summary'],
        embeddings_df['Text'],
        embeddings_df['combined'],
        embeddings_df['vector']
    ))

    # Insert embeddings into the database
    if st.button("Insert Pre-Generated Embeddings into Database"):
        try:
            conn = get_mssql_connection()
            cursor = conn.cursor()
            cursor.fast_executemany = True  # Enable fast execution for batch insertion

            query = """
            INSERT INTO embeddings (Id, ProductId, UserId, score, summary, text, combined, vector)
            VALUES (?, ?, ?, ?, ?, ?, ?, CAST(CAST(? AS VARCHAR(MAX)) AS VECTOR(1536)))
            """

            # ✅ Insert in chunks for better memory handling
            batch_size = 1000
            for i in range(0, len(data_to_insert), batch_size):
                cursor.executemany(query, data_to_insert[i:i+batch_size])

            conn.commit()
            conn.close()
            st.success("Pre-generated embeddings inserted into the database successfully!")
        except Exception as e:
            st.error(f"An error occurred: {e}")

# ---------------------------
# Section 5: Perform Vector Search
# ---------------------------
st.subheader("Step 5: Perform Vector Search")

with st.expander("**Vector Search and Completion**"):
    st.markdown(""" 
Let's now query our embedding table to get the top similar reviews given the User search query.

What we are doing: Given any user search query, we can get the vector representation of that text.

Then we can use that vector to calculate the **cosine distance** against all the customer review comments stored in the database and take only the closest ones which will return the product most likely connected to the product we are interested in.
                
**SQL Query:**
                """)
    st.code("""
           SELECT TOP(?) ProductId, Summary, text,               
                VECTOR_DISTANCE('cosine', @e, Vector) AS Distance
            FROM dbo.embeddings
            ORDER BY Distance;
            """)

# Input fields
user_query = st.text_input("Enter your search query")
num_results = st.number_input("Number of results to retrieve", min_value=1, max_value=100, value=5)

# Clear session state button
if st.button("Clear Results"):
    st.session_state.pop('search_results', None)
    st.session_state.pop('last_user_query', None)
    st.session_state.pop('last_num_results', None)
    st.success("Previous search results cleared!")

# Vector search function
def vector_search_sql(query, num_results):
    conn = get_mssql_connection()
    cursor = conn.cursor()
    user_query_embedding = get_embedding(query)
    user_query_embedding_json = json.dumps(user_query_embedding)
    sql_similarity_search = """
    SELECT TOP(?) ProductId, Summary, text,
           1 - vector_distance('cosine', CAST(CAST(? AS VARCHAR(MAX)) AS VECTOR(1536)), [vector]) AS similarity_score
    FROM dbo.embeddings
    ORDER BY similarity_score DESC
    """
    cursor.execute(sql_similarity_search, (num_results, user_query_embedding_json))
    results = cursor.fetchall()
    conn.close()
    return results

# Run search only on button click
if st.button("Vector Search"):
    if user_query:
        # Reset if query or num_results changed
        if (
            st.session_state.get('last_user_query') != user_query or
            st.session_state.get('last_num_results') != num_results
        ):
            st.session_state.pop('search_results', None)

        search_results = vector_search_sql(user_query, num_results)
        st.session_state['search_results'] = search_results
        st.session_state['last_user_query'] = user_query
        st.session_state['last_num_results'] = num_results
    else:
        st.error("Please enter a search query.")

# Display results
if st.session_state.get('search_results') is not None:
    st.write("### Search Results:")
    for result in st.session_state['search_results']:
        st.write(f"**Product ID:** {result[0]}")
        st.write(f"**Summary:** {result[1]}")
        st.write(f"**Text:** {result[2]}")
        st.write(f"**Similarity Score:** {result[3]:.4f}")
        st.write("---")

# ---------------------------
# Section 6: Augment LLM Generation
# ---------------------------
st.subheader("Step 6: Augument LLM Generation")
with st.expander("**Augment LLM Generation**"):
    st.markdown("""
    A helper function is created to feed prompts into the **OpenAI Completions model** & create interactive loop where you can pose questions to the model and receive information grounded in your data.

The function `generate_completion` is defined to help ground the GPT 4.1 model with prompts and system instructions. 
We are passing the results of the `vector_search_sql` function to the model and we define the system prompt as follows:
                """)
    st.code("""
    system_prompt = '''
    You are an intelligent & funny assistant who will exclusively answer based on the data provided in the `search_results`:
    - Use the information from `search_results` to generate your responses. If the data is not a perfect match for the user's query, use your best judgment to provide helpful suggestions and include the following format:
      Product ID: {product_id}
      Summary: {summary}
      Review: {text}
      Similarity Score: {similarity_score}
    - Avoid any other external data sources.
    - Rank them from most relevant to least.
    - End with a "Final Summary" paragraph that summarizes the overall findings and suggests the best pick.
    - Add a fun fact related to the overall product searched at the end of the recommendations.
    - Tone: Helpful, conversational, and slightly playful.
    - Add emojis for ranking (🔥 for top pick, ⭐ for others).
            """)
    
# Azure OpenAI client
client = AzureOpenAI(
    api_key=os.getenv('AZURE_OPENAI_API_KEY'),
    api_version="2023-05-15",
    azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT')
)

def generate_completion(search_results, user_query):
    system_prompt = '''
    You are an intelligent & funny assistant who will exclusively answer based on the data provided in the `search_results`:
    - Use the information from `search_results` to generate your responses. If the data is not a perfect match for the user's query, use your best judgment to provide helpful suggestions and include the following format:
      Product ID: {product_id}
      Summary: {summary}
      Review: {text}
      Similarity Score: {similarity_score}
    - Avoid any other external data sources.
    - Rank them from most relevant to least.
    - End with a "Final Summary" paragraph that summarizes the overall findings and suggests the best pick.
    - Add a fun fact related to the overall product searched at the end of the recommendations.
    - Tone: Helpful, conversational, and slightly playful.
    - Add emojis for ranking (🔥 for top pick, ⭐ for others).
    '''

    messages = [{"role": "system", "content": system_prompt}]
    result_list = [
        {
            "product_id": r[0],
            "summary": r[1],
            "text": r[2],
            "similarity_score": r[3]
        }
        for r in search_results
    ]
    messages.append({"role": "system", "content": f"{result_list}"})
    messages.append({"role": "user", "content": user_query})

    response = client.chat.completions.create(
        model='gpt-4.1',
        messages=messages,
        temperature=0
    )
    return response.model_dump()

if st.button("Generate Response"):
    if user_query:
        try:
            # Use cached results if query unchanged
            if (
                st.session_state.get('search_results') is not None and
                st.session_state.get('last_user_query') == user_query and
                st.session_state.get('last_num_results') == num_results
            ):
                search_results = st.session_state['search_results']
            else:
                search_results = vector_search_sql(user_query, num_results)
                st.session_state['search_results'] = search_results
                st.session_state['last_user_query'] = user_query
                st.session_state['last_num_results'] = num_results

            completion_response = generate_completion(search_results, user_query)
            st.write("### Generated Response:")
            st.write(completion_response['choices'][0]['message']['content'])
        except Exception as e:
            st.error(f"An error occurred: {e}")
    else:
        st.error("Please enter a search query.")
# ---------------------------
