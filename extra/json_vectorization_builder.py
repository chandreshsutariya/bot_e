from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import SentenceTransformerEmbeddings
import json
import os

with open("files/database_schema.json") as f:
    schema = json.load(f)

with open("files/database_description.json") as f:
    description = json.load(f)

schema_text = json.dumps(schema, indent=2)
description_text = json.dumps(description, indent=2)
full_text = schema_text + "\n\n" + description_text

text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
documents = text_splitter.create_documents([full_text])

embedding_model = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
vectorstore = FAISS.from_documents(documents, embedding=embedding_model)

vectorstore.save_local("db_schema_vector_index")