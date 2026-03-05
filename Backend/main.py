import os
import json
import time
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from dotenv import load_dotenv

from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from reranker import CrossEncoderReranker
from hybrid_retriever import HybridRetriever


# -----------------------------
# ENV + CONFIG
# -----------------------------
load_dotenv()

INDEX_DIR = os.getenv("INDEX_DIR", "E:/Flask/Playage_Support_Bot/Version-1.0/Backend/RAG/faq_vector_index")
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
GEMINI_API_KEY = os.getenv("GEMINI_API")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY_3")

FAISS_K = int(os.getenv("FAISS_K", "12"))
BM25_K = int(os.getenv("BM25_K", "12"))
RERANK_TOP_N = int(os.getenv("RERANK_TOP_N", "5"))
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "12000"))

RATE_LIMIT_RPS = float(os.getenv("RATE_LIMIT_RPS", "3.0"))
RATE_BUCKET: Dict[str, List[float]] = {}

# -----------------------------
# FASTAPI APP
# -----------------------------
app = FastAPI(title="Playage Backoffice RAG API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# REQUEST / RESPONSE SCHEMAS
# -----------------------------
class AskRequest(BaseModel):
    Username: str = Field(..., max_length=30)
    User_preffered_language: str = Field(..., pattern="^(en|tr)$")
    question: str = Field(..., min_length=2, max_length=2000)
    top_k: Optional[int] = Field(None, ge=1, le=20)


class AskResponse(BaseModel):
    Definition: str
    Steps: List[str]
    Tips: List[str]
    Image_References: str
    References: str = ""


# -----------------------------
# PROMPT (NO f-string!)
# -----------------------------
def build_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_template("""
You are the Playage Backoffice Support Assistant, an intelligent and highly professional AI routing and support agent. 

Your job is to analyze the user's input, deduce their intent, and respond accordingly. You decide whether to act as a conversational partner (for greetings) or as a strict RAG-based documentation assistant.

User Information:
- Username: {username}
- Preferred Language: {language} (You MUST respond in this language)

Current UTC Time: {current_utc_time}

YOUR LOGIC FLOW:
1. GREETINGS & CASUAL CHAT: 
   - If the user explicitly says hello, asks how you are, expresses gratitude, or makes casual small talk, respond warmly and professionally in the "Definition" field. Greet them by their Username.
   - Ignore the CONTEXT in this case. Do not say "information is missing" for a simple greeting.

2. VAGUE OR INCOMPLETE QUESTIONS:
   - If the user asks a question with missing context, pronouns without clear referents (e.g., "How is this helpful?", "What does it do?"), or a question too broad to answer accurately without knowing what they are looking at:
   - Do NOT attempt to guess based on the CONTEXT.
   - Politely ask the user to clarify what specific feature, page, or action they are referring to in the "Definition" field.

3. PLAYAGE SUPPORT QUESTIONS (RAG):
   - If the user asks a specific question related to Playage Backoffice, features, system actions, or documentation, you MUST act as a strict documentation assistant.
   - Examine the provided CONTEXT. 
   - If the CONTEXT contains the answer, summarize it into "Definition", extract any chronological actions into "Steps", list additional advice as "Tips", and grab "Image_References".
   - CRITICAL IMAGE RULE: If you provide an `Image_References`, it MUST be ONLY the raw, exact URL. Do NOT include phrases like "Reference screenshot for documentation purposes:", do NOT say "Here is the image", do NOT include the URL in the `Definition` text. The frontend displays the image automatically using the URL. If no text explanation is needed, set `Definition` to exactly "".
   - If the CONTEXT is empty or does NOT contain the answer, you MUST respond exactly with "This information is not available in the documentation." (or its equivalent in the user's preferred language) under "Definition". Do NOT attempt to guess or use outside knowledge.

4. OUT-OF-SCOPE QUESTIONS:
   - If the user asks general world knowledge (e.g., "What is the capital of France?" or "Write a poem"), refuse politely using the "Definition" field, stating that you are dedicated to Playage Backoffice support only.

MANDATORY OUTPUT FORMAT (JSON ONLY):
{{
  "Definition": "<Your primary response or explanation.>",
  "Steps": [], 
  "Tips": [], 
  "Image_References": "<Pure valid URL to image, or empty string>"
}}

Rules for JSON:
- If Steps or Tips are not applicable, leave as empty arrays [].
- If no Image References, leave as an empty string "".
- Do NOT add any extra fields. 
- Do NOT wrap your JSON in markdown code blocks like ```json ... ```. Just return the raw JSON text.
- ALL generated text in the JSON (Definition, Steps, Tips) MUST be in the user's preferred language ({language}).

----------------------------------------------------
CONTEXT:
{context}

----------------------------------------------------
USER QUESTION:
{question}
""")


# -----------------------------
# GLOBALS
# -----------------------------
embedding_model = None
vectorstore = None
hybrid_retriever = None
reranker = None
llm_primary = None
llm_backup = None


@app.on_event("startup")
def startup():
    global embedding_model, vectorstore, hybrid_retriever, reranker, llm_primary, llm_backup

    if not GEMINI_API_KEY:
        print("Warning: Missing GEMINI_API key. Gemini will not work as primary.")
    if not CEREBRAS_API_KEY:
        raise RuntimeError("Missing CEREBRAS_API_KEY_3")

    embedding_model = HuggingFaceEmbeddings(model_name=EMBED_MODEL)

    vectorstore = FAISS.load_local(
        INDEX_DIR,
        embedding_model,
        allow_dangerous_deserialization=True,
    )

    faiss_retriever = vectorstore.as_retriever(search_kwargs={"k": FAISS_K})
    all_docs = list(vectorstore.docstore._dict.values())

    hybrid_retriever = HybridRetriever(
        faiss_retriever=faiss_retriever,
        documents=all_docs,
    )

    reranker = CrossEncoderReranker(top_n=RERANK_TOP_N)

    llm_primary = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=GEMINI_API_KEY,
        temperature=0.2,
        convert_system_message_to_human=True,
    )
    
    llm_backup = ChatOpenAI(
        base_url="https://api.cerebras.ai/v1",
        openai_api_key=CEREBRAS_API_KEY,
        model="gpt-oss-120b",
        temperature=0.2,
        model_kwargs={
            "response_format": {"type": "json_object"}
        }
    )

    print("✅ API Ready")


# -----------------------------
# HELPERS
# -----------------------------
def rate_limit(ip: str):
    now = time.time()
    bucket = RATE_BUCKET.setdefault(ip, [])
    bucket[:] = [t for t in bucket if now - t < 1]

    if len(bucket) >= RATE_LIMIT_RPS:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    bucket.append(now)


def safe_json_parse(s: str) -> Dict[str, Any]:
    s = s.strip()
    if s.startswith("```"):
        s = s.strip("`").strip()
        if s.lower().startswith("json"):
            s = s[4:].strip()
    return json.loads(s)


def empty_answer() -> AskResponse:
    return AskResponse(
        Definition="This information is not available in the documentation.",
        Steps=[],
        Tips=[],
        Image_References="",
        References="",
    )


def build_context(docs) -> str:
    parts = []
    total = 0

    for d in docs:
        block = (
            f"Document: {d.metadata.get('title')}\n"
            f"Section: {d.metadata.get('section')}\n"
            f"{d.page_content}\n"
        )

        if total + len(block) > MAX_CONTEXT_CHARS:
            print("[Context length exceeded, stopping concatenation]")
            break

        parts.append(block)
        total += len(block)

    final_context = "\n\n".join(parts)
    print("\n=== FINAL CONTEXT SENT TO LLM ===")
    print(final_context)
    print("=================================\n")

    return final_context


# -----------------------------
# ROUTE
# -----------------------------
@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest, request: Request):

    rate_limit(request.client.host)

    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Empty question")

    docs = hybrid_retriever.search(question, k_faiss=FAISS_K, k_bm25=BM25_K)

    context = ""
    references_text = ""
    if docs:
        reranker.top_n = req.top_k or RERANK_TOP_N
        docs = reranker.rerank(question, docs)
        context = build_context(docs)
        
        ref_list = []
        seen_urls = set()
        for d in docs:
            title = d.metadata.get('title')
            doc_id = d.metadata.get('doc_id')
            if title and doc_id:
                url = f"https://userguide.playagegaming.tech/en/bo/{doc_id}/"
                if url not in seen_urls:
                    ref_list.append(f"{title}\n   {url}")
                    seen_urls.add(url)
                    
        if ref_list:
            formatted_refs = [f"{i}. {ref}" for i, ref in enumerate(ref_list, 1)]
            references_text = "---\nReferences:\n" + "\n".join(formatted_refs)

    prompt = build_prompt()

    try:
        formatted_prompt = prompt.format(
            context=context,
            question=question,
            username=req.Username,
            language=req.User_preffered_language,
            current_utc_time=datetime.now(timezone.utc).isoformat(),
        )

        try:
            print("Invoking Gemini (Primary)...")
            raw = llm_primary.invoke(formatted_prompt).content
        except Exception as e_primary:
            print(f"Gemini API failed with error: {e_primary}. Falling back to Cerebras...")
            raw = llm_backup.invoke(formatted_prompt).content

        data = safe_json_parse(raw)
        
        definition_text = data.get("Definition", "Not available")
        is_fallback = "not available" in definition_text.lower()
        
        return AskResponse(
            Definition=definition_text,
            Steps=data.get("Steps", []),
            Tips=data.get("Tips", []),
            Image_References=data.get("Image_References", ""),
            References="" if is_fallback or not context else references_text,
        )
    except Exception as e:
        print(f"Error processing answer: {e}")
        return empty_answer()