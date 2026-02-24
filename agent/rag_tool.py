# # agent/rag_tool.py

# import os 
# from langchain_community.vectorstores import FAISS
# from langchain_huggingface import HuggingFaceEmbeddings
# from langchain_community.document_loaders import PyPDFLoader
# # from langchain_text_splitter import RecursiveCharacterTextSplitter
# from langchain_text_splitters import RecursiveCharacterTextSplitter
# from langchain.chains import RetrievalQA
# from langchain_openai import ChatOpenAI
# from langchain_google_genai import ChatGoogleGenerativeAI
# from dotenv import load_dotenv
# load_dotenv()
# GEMINI_API_KEY = os.getenv("GEMINI_API")
# retriever = None
# INDEX_DIR = "faq_vector_index"
# PDF_PATH = "files/oppiWallet_FAQ _updated.pdf"

# embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# def load_pdf_retriever(pdf_path: str = PDF_PATH):
#     global retriever
#     if retriever:
#         return retriever
    
#     if os.path.exists(INDEX_DIR):
#         vectorstore = FAISS.load_local(INDEX_DIR, embedding_model, allow_dangerous_deserialization=True)
#         retriever = vectorstore.as_retriever()
#         return retriever

#     loader = PyPDFLoader(pdf_path)
#     docs = loader.load()

#     splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
#     chunks = splitter.split_documents(docs)

#     vectorstore = FAISS.from_documents(chunks, embedding=embedding_model)

#     vectorstore.save_local(INDEX_DIR)

#     retriever = vectorstore.as_retriever()
#     return retriever

# def answer_from_faq(question: str) -> str:
#     llm = ChatOpenAI(
#         base_url="https://api.cerebras.ai/v1",
#         openai_api_key=os.getenv("CEREBRAS_API_KEY_OPPI_2"),
#         model="llama-3.3-70b",
#         temperature=0.3,
#         top_p=0.5,
#     )
    
#     retriever = load_pdf_retriever()
#     qa_chain = RetrievalQA.from_chain_type(
#         llm=llm,
#         retriever=retriever,
#         return_source_documents=False
#     )
#     return qa_chain.invoke(question)
import os
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

from langchain_core.prompts import ChatPromptTemplate
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.chains import create_retrieval_chain

from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API")

retriever = None
INDEX_DIR = "faq_vector_index"
PDF_PATH = "files/oppiWallet_FAQ_updated_latest.pdf"

embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

def build_vector_index(pdf_path: str):
    loader = PyPDFLoader(pdf_path)
    docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(docs)

    vectorstore = FAISS.from_documents(chunks, embedding_model)
    vectorstore.save_local(INDEX_DIR)

    return vectorstore

def load_pdf_retriever(pdf_path: str = PDF_PATH):
    global retriever

    if retriever is not None:
        return retriever

    try:
        if os.path.exists(INDEX_DIR):
            vectorstore = FAISS.load_local(
                INDEX_DIR,
                embeddings=embedding_model,
                allow_dangerous_deserialization=True
            )
        else:
            vectorstore = build_vector_index(pdf_path)
    except Exception:
        # If corrupted — rebuild index
        vectorstore = build_vector_index(pdf_path)

    retriever = vectorstore.as_retriever(search_kwargs={"k": 5}) #
    return retriever

def answer_from_faq(question: str) -> str:
    # llm = ChatOpenAI(
    #     base_url="https://api.cerebras.ai/v1",
    #     openai_api_key=os.getenv("CEREBRAS_API_KEY_OPPI_2"),
    #     model="llama-3.3-70b",
    #     temperature=0.3,
    #     top_p=0.5
    # )

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", 
        google_api_key=GEMINI_API_KEY,
        temperature=0.3,
        convert_system_message_to_human=True,
        top_p=0.5,
    )

    retriever = load_pdf_retriever()

    # prompt = ChatPromptTemplate.from_template(
    #     f"""You are a support FAQ assistant.

    #     Use ONLY the information provided in the context to answer the question.

    #     Rules:
    #     - If the answer is found in the context, respond clearly and concisely.
    #     - If the question is unclear or incomplete, ask the user politely for more information.
    #     - If the answer is NOT in the context, say:
    #         "I couldn’t find this in the FAQ. Please contact support."
    #     - Do NOT add unnecessary or additional information or irrelevent information which is not belongs to user's ask.
    #     - Do NOT make up information.
    #     - Do NOT include context in your answer.
    #     - Keep answers under 3–4 sentences."""
    #     "Context:\n{context}\n\nQuestion: {input}\nAnswer:"
    # )
    prompt = ChatPromptTemplate.from_template(
    """
        You are a support FAQ assistant. Your task is to determine whether the provided context contains the answer to the user's question.

        Follow this strict two-step process:
        1. Carefully read the provided context.
        2. Decide whether the context includes enough information to answer the user's question.

        Response Rules:
        - If the answer IS found in the context, answer using ONLY information from the context. Keep the answer clear and concise (3–4 sentences max).
        - If the answer is NOT found in the context, respond with EXACTLY:
        "I couldn’t find this in the Knowledge Base. Please contact support."
        - Do NOT use any outside knowledge.
        - Do NOT add or invent information.

        Context:
        {context}

        Question:
        {input}

        Answer:
        """
        )


    # qa_chain = RetrievalQA.from_chain_type(
    #     llm=llm,
    #     retriever=retriever,
    #     return_source_documents=False
    # )

    # return qa_chain.invoke(question)

    combine_docs_chain = create_stuff_documents_chain(llm, prompt) #prompt
    retrieval_chain = create_retrieval_chain(
        retriever=retriever,
        combine_docs_chain=combine_docs_chain,
    )

    return retrieval_chain.invoke({"input": question})
    # answer = result.get("answer") or result.get("output") or str(result)
    # return answer
    