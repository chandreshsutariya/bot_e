from rank_bm25 import BM25Okapi
from langchain_core.documents import Document
import re

class HybridRetriever:
    def __init__(self, faiss_retriever, documents):
        """
        faiss_retriever: LangChain FAISS retriever
        documents: list[Document] – same docs used to build FAISS
        """
        self.faiss_retriever = faiss_retriever
        self.documents = documents

        # Prepare corpus for BM25
        self.tokenized_corpus = [
            self._tokenize(doc.page_content) for doc in documents
        ]
        self.bm25 = BM25Okapi(self.tokenized_corpus)

    def _tokenize(self, text: str):
        return re.findall(r"\w+", text.lower())

    def search(self, query: str, k_faiss=8, k_bm25=8):
        import copy
        
        # FAISS search
        faiss_docs = self.faiss_retriever.invoke(query)
        faiss_docs_copy = []
        for doc in faiss_docs:
            doc_copy = copy.deepcopy(doc)
            doc_copy.metadata["retrieval_source"] = "FAISS (Semantic)"
            faiss_docs_copy.append(doc_copy)

        # BM25 search
        tokenized_query = self._tokenize(query)
        bm25_scores = self.bm25.get_scores(tokenized_query)
        top_bm25_indices = sorted(
            range(len(bm25_scores)),
            key=lambda i: bm25_scores[i],
            reverse=True
        )[:k_bm25]

        bm25_docs_copy = []
        for i in top_bm25_indices:
            doc_copy = copy.deepcopy(self.documents[i])
            doc_copy.metadata["retrieval_source"] = "BM25 (Keyword)"
            bm25_docs_copy.append(doc_copy)

        # Merge & deduplicate
        combined = {}
        for doc in faiss_docs_copy + bm25_docs_copy:
            key = (doc.metadata.get("doc_id"), doc.metadata.get("section"))
            if key in combined:
                if combined[key].metadata.get("retrieval_source") != doc.metadata.get("retrieval_source"):
                    combined[key].metadata["retrieval_source"] = "FAISS + BM25"
            else:
                combined[key] = doc

        return list(combined.values())