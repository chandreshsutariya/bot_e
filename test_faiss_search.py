"""
Step 5 – Option 1
FAISS Search Tester (No LLM)

Purpose:
- Load FAISS index
- Run similarity search
- Inspect retrieved chunks + metadata
"""

from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from pathlib import Path

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
INDEX_DIR = "E:/Flask/Playage_Support_Bot/Embedding/faq_vector_index"
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

TOP_K = 5  # number of chunks to retrieve


# -------------------------------------------------
# LOAD VECTOR STORE
# -------------------------------------------------
def load_vectorstore():
    print("🔄 Loading embedding model...")
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME
    )

    print("🔄 Loading FAISS index...")
    vectorstore = FAISS.load_local(
        INDEX_DIR,
        embeddings,
        allow_dangerous_deserialization=True
    )

    print("✅ FAISS index loaded")
    return vectorstore


# -------------------------------------------------
# SEARCH FUNCTION
# -------------------------------------------------
def search(vectorstore, query: str, top_k: int = TOP_K):
    print(f"\n🔎 Query: {query}\n")

    results = vectorstore.similarity_search(
        query=query,
        k=top_k
    )

    for i, doc in enumerate(results, start=1):
        print("=" * 80)
        print(f"Result #{i}")
        print("-" * 80)

        metadata = doc.metadata

        print(f"📄 Document Title : {metadata.get('title')}")
        print(f"📑 Section        : {metadata.get('section_heading')}")
        print(f"📂 Category       : {metadata.get('category')}")
        print(f"🧩 Topic ID       : {metadata.get('topic_id')}")
        print(f"🖼 Has Image      : {metadata.get('has_image')}")

        print("\n📝 Content Preview:")
        print(doc.page_content[:800])  # preview first 800 chars
        print("\n")

    print("=" * 80)
    print("✅ Search complete\n")


# -------------------------------------------------
# MAIN (CLI LOOP)
# -------------------------------------------------
def main():
    vectorstore = load_vectorstore()

    print("\n💡 FAISS Search Tester")
    print("Type a question and press Enter")
    print("Type 'exit' to quit\n")

    while True:
        query = input("❓ Question: ").strip()

        if query.lower() in {"exit", "quit"}:
            print("👋 Exiting search tester")
            break

        if not query:
            continue

        search(vectorstore, query)


if __name__ == "__main__":
    main()
