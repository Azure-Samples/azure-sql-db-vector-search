# Create, store and query OpenAI embeddings in Azure SQL DB

This notebook will teach you to:

- How to create embeddings from content using the Azure OpenAI API
- How to use Azure SQL DB as a vector database and store embeddings data in SQL & perform similarity search
- How to use embeddings retrieved from a vector database to augment LLM generation.

We will be using the Fine Foods Review Dataset available on Kaggle. This dataset consists of reviews of fine foods from amazon
For the tutorial we will be using a smaller sample for the tutorial that can be downloaded here

If you want to skip the steps of generating embeddings & directly load it in SQLDB to perform similarity search you can download the finefoodembeddings.csv file that contains generated embeddings using text-embedding-small model from Azure OpenAI.

This notebook contains some code snippets from the documentation Explore [Azure OpenAI Service embeddings Tutorial](https://learn.microsoft.com/en-us/azure/ai-services/openai/tutorials/embeddings?tabs=python-new%2Ccommand-line&pivots=programming-language-python)
