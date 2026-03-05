"""
Step : FAISS Embedding Pipeline

Input  : chunks.json
Output : faq_vector_index/ (FAISS index folder)

This script:
- Loads structured chunks
- Converts to LangChain Documents
- Embeds using MiniLM
- Builds FAISS index
- Saves locally
"""

import json
from pathlib import Path
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
CHUNKS_FILE = "E:/Flask/Playage_Support_Bot/chandresh_sir_data_chunks.json"
INDEX_DIR = "E:/Flask/Playage_Support_Bot/Embedding/chandresh_data_faq_vector_index"

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
# EMBEDDING_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# -------------------------------------------------
# LOAD CHUNKS
# -------------------------------------------------
def load_chunks(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# -------------------------------------------------
# CONVERT TO LANGCHAIN DOCUMENTS
# -------------------------------------------------
def convert_to_documents(chunks):
    documents = []

    for chunk in chunks:
        doc = Document(
            page_content=chunk["text"],
            metadata={
                "chunk_id": chunk["chunk_id"],
                "doc_id": chunk["doc_id"],
                "title": chunk.get("title"),
                "section_heading": chunk.get("section_heading"),
                "module": chunk.get("module"),
                "category": chunk.get("category"),
                "topic_id": chunk.get("topic_id"),
                "level": chunk.get("level"),
                "priority": chunk.get("priority"),
                "has_image": chunk.get("has_image"),
            }
        )
        documents.append(doc)

    return documents


# -------------------------------------------------
# BUILD FAISS INDEX
# -------------------------------------------------
def build_faiss_index(documents):
    print("🔄 Loading embedding model...")
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME
    )

    print("🔄 Creating FAISS index...")
    vectorstore = FAISS.from_documents(documents, embeddings)

    print("💾 Saving index...")
    vectorstore.save_local(INDEX_DIR)

    print("✅ FAISS index built successfully at", INDEX_DIR)


# -------------------------------------------------
# MAIN
# -------------------------------------------------
def main():
    chunks_path = Path(CHUNKS_FILE)

    if not chunks_path.exists():
        raise FileNotFoundError("chunks.json not found. Run Step 3 first.")

    print("📄 Loading chunks...")
    chunks = load_chunks(chunks_path)

    print(f"📦 Total chunks loaded: {len(chunks)}")

    documents = convert_to_documents(chunks)

    build_faiss_index(documents)


if __name__ == "__main__":
    main()




#current result:
'''
📄 Loading chunks...
📦 Total chunks loaded: 596
🔄 Loading embedding model...
🔄 Creating FAISS index...
💾 Saving index...
✅ FAISS index built successfully at E:/Flask/Playage_Support_Bot/Embedding/faq_vector_index !
'''