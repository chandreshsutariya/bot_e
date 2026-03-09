import os
import re
import json
import time
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from dotenv import load_dotenv

from langchain_community.vectorstores import FAISS
from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage
try:
    from google.api_core.exceptions import ResourceExhausted as GeminiResourceExhausted
except ImportError:
    GeminiResourceExhausted = None  # graceful — won't affect fallback logic

from reranker import CrossEncoderReranker
from hybrid_retriever import HybridRetriever
import warnings
from requests.exceptions import RequestsDependencyWarning
warnings.filterwarnings("ignore", category=RequestsDependencyWarning)

# -----------------------------
# ENV + CONFIG
# -----------------------------
load_dotenv()

INDEX_DIR = os.getenv("INDEX_DIR", "E:/Flask/Playage_Support_Bot/Version-1.0/Backend/RAG/Embedding/faq_vector_index")
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
GEMINI_API_KEY = os.getenv("GEMINI_API")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY_3")

FAISS_K = int(os.getenv("FAISS_K", "12"))
BM25_K = int(os.getenv("BM25_K", "12"))
RERANK_TOP_N = int(os.getenv("RERANK_TOP_N", "5"))
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "12000"))
MEMORY_TURNS = int(os.getenv("MEMORY_TURNS", "6"))

RATE_LIMIT_RPS = float(os.getenv("RATE_LIMIT_RPS", "3.0"))
RATE_BUCKET: Dict[str, List[float]] = {}

MEMORY_DIR = os.getenv("MEMORY_DIR", "memory_sessions")
os.makedirs(MEMORY_DIR, exist_ok=True)

# Mandatory client-side secret — all /ask requests must include this
BACKEND_API_KEY = os.getenv("BACKEND_SECRET_KEY", "playage-bo-secret-2024")

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
    session_id: Optional[str] = Field(None, max_length=64)
    api_key: str = Field(...)   # mandatory — must match BACKEND_API_KEY


class SessionDeleteRequest(BaseModel):
    session_id: str = Field(..., max_length=64)
    api_key: str = Field(...)


class AskResponse(BaseModel):
    Definition: str
    Steps: List[str]
    Follow_Up_Questions: List[str] = []  # clickable chips on frontend
    Image_References: List[str] = []
    Video_References: List[str] = []
    References: str = ""
    Intent: str = "documentation"  # greeting|conversational|documentation|out_of_scope|clarification_needed


# -----------------------------
# PROMPT (NO f-string!)
# -----------------------------
def build_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_template("""
You are the Playage Backoffice Support Assistant — a knowledgeable, professional, and friendly AI support agent.

User: {username} | Preferred Language: {language} | Time: {current_utc_time}

----------------------------------------------------
CONVERSATION HISTORY:
{chat_history}
----------------------------------------------------

=== LANGUAGE DETECTION (apply before anything else) ===

1. Detect the language the user wrote their CURRENT MESSAGE in.
2. If the user's message is in a DIFFERENT language than {language}, respond in the user's detected language.
3. If it matches {language}, respond in {language}.
The bot always mirrors the user's actual writing language — not just the configured preference.
Examples: Persian message → Persian reply | Turkish message → Turkish reply | English → English.
Apply to ALL text fields (Definition, Steps, Follow_Up_Questions).

=== STEP 1 — INTENT IDENTIFICATION ===

Classify the user's message into exactly ONE of these intents:

- "greeting"             → hello, hi, hey, good morning, greetings
- "conversational"       → thanks, okay, got it, great, understood, noted, perfect,
                           single-word acknowledgements in any language (باشه, tamam, evet, etc.)
- "new_user"             → user says they are new, don't know the platform, need a guide,
                           want an overview, or asks "where do I start?"
- "documentation"        → any specific question about Playage Backoffice features,
                           workflows, settings, reports, pages, or processes
- "out_of_scope"         → questions completely unrelated to Playage Backoffice
- "clarification_needed" → too vague and none of the above fit

=== STEP 2 — RESPOND BASED ON INTENT ===

**greeting:**
- Definition: greet the user warmly by name (1 sentence).
- All other fields → empty [].

**conversational:**
- Definition: respond warmly and in a friendly, human way. NEVER use cold one-word replies like "Understood." or "Noted."
  Instead, briefly acknowledge what the user said AND gently invite them to continue.
  Examples of good responses:
    - "Got it, Mahesh! Feel free to ask anything about the Playage Backoffice — I'm here to help."
    - "Sure thing! Let me know whenever you're ready to explore something specific."
    - "Of course! happy to help anytime. Just let me know what you'd like to know next."
  Use {username} where natural. Mirror the user's language.
- All other fields → empty [].

**new_user:**
- The user is brand new and needs a welcoming orientation to the platform.
- Definition: 2–3 friendly sentences explaining what Playage Backoffice is
  (a comprehensive gaming back-office management platform for operators to manage players, finance, bonuses, and analytics).
- Steps: List 6–7 key areas they can explore, each as a short action phrase:
    "Explore User Management — view, search, and manage player accounts"
    "Check Financial Reports — daily sales, revenue, and transaction history"
    "Manage Bonuses — create and assign bonus campaigns to players"
    "Review the Dashboard — real-time overview of platform activity"
    "Configure Settings — system preferences and integrations"
    "Access Player Analytics — monitor player behaviour and trends"
    "Use the Ticket System — handle support requests from players"
- Follow_Up_Questions: 2–3 helpful starter questions like "How do I view a player's account?" or "Where can I find daily sales reports?"
- Image_References, Video_References → empty [].

**clarification_needed:**
- Definition: ask a specific clarifying question (not generic "how can I help?").
- All other fields → empty [].

**out_of_scope:**
- Definition: politely explain this is outside your support scope.
- All other fields → empty [].

**documentation:**
- Read the CONTEXT carefully.
- Definition: if Steps exist → write a short 1-sentence intro only. Do NOT repeat the steps in Definition.
            if no Steps → write a concise paragraph answer.
- Steps: clean numbered action steps. Empty [] if no sequential actions.
- Follow_Up_Questions: 2–3 natural next questions. Question strings only.
- Image_References: ONLY images directly answering the question. Max 3. Exact raw URLs only.
- Video_References: Most relevant video only. Max 1. Exact raw URL only.
- If CONTEXT is empty or doesn't answer: Definition = "This information is not available in the documentation."

=== OUTPUT FORMAT (RAW JSON ONLY — NO MARKDOWN FENCES) ===
{{
  "Intent": "<one of: greeting | conversational | new_user | documentation | out_of_scope | clarification_needed>",
  "Definition": "<response text>",
  "Steps": [],
  "Follow_Up_Questions": [],
  "Image_References": [],
  "Video_References": []
}}

Strict rules:
- RAW JSON only. Never wrap in ```json fences.
- Mirror the user's writing language as described above.
- Exactly 6 fields. Nothing else.
- No URLs in Definition.

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
        max_retries=0,   # ← disable LangChain's own 32-second retry loop
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


# -----------------------------
# MEMORY HELPERS
# -----------------------------
def get_session_history(session_id: str) -> FileChatMessageHistory:
    """Return (or create) a file-backed message history for the given session."""
    safe_id = re.sub(r'[^\w\-]', '_', session_id)[:64]
    path = os.path.join(MEMORY_DIR, f"{safe_id}.json")
    return FileChatMessageHistory(file_path=path)


def format_chat_history(history: FileChatMessageHistory, max_turns: int = MEMORY_TURNS) -> str:
    """Format the last max_turns message pairs as a readable string for the prompt."""
    messages = history.messages
    # Keep only the last max_turns * 2 messages (each turn = 1 human + 1 ai)
    messages = messages[-(max_turns * 2):]
    if not messages:
        return "No previous conversation."
    lines = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            lines.append(f"User: {msg.content}")
        elif isinstance(msg, AIMessage):
            lines.append(f"Assistant: {msg.content}")
    return "\n".join(lines)


# Regex patterns to extract media URLs from raw context text
_IMG_RE = re.compile(r'https?://\S+\.(?:webp|png|jpg|jpeg|gif)', re.IGNORECASE)
_VID_RE = re.compile(r'https?://\S+\.(?:mp4|webm|ogg|mov)', re.IGNORECASE)


def extract_media_from_context(context: str):
    """Extract all image and video URLs from the raw context string (deduped, order-preserved)."""
    images = list(dict.fromkeys(_IMG_RE.findall(context)))
    videos = list(dict.fromkeys(_VID_RE.findall(context)))
    return images, videos


def merge_dedup(llm_list, context_list):
    """Merge two lists, keeping LLM-provided items first, then adding any extras from context."""
    seen = set()
    result = []
    for url in llm_list + context_list:
        url = url.strip().rstrip(')')
        if url and url not in seen:
            seen.add(url)
            result.append(url)
    return result


def empty_answer() -> AskResponse:
    return AskResponse(
        Definition="This information is not available in the documentation.",
        Steps=[],
        Follow_Up_Questions=[],
        Image_References=[],
        Video_References=[],
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

    if req.api_key != BACKEND_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized: invalid API key")

    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Empty question")

    # ── MEMORY: load per-session history ─────────────────────────────────────
    session_id = req.session_id or f"anon_{req.Username}"
    history = get_session_history(session_id)
    chat_history_text = format_chat_history(history)
    print(f"[Memory] session={session_id}, turns={len(history.messages)}")

    # ── RAG: always retrieve — intent filtering done by the LLM itself ─────────
    docs = hybrid_retriever.search(question + chat_history_text, k_faiss=FAISS_K, k_bm25=BM25_K)

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
            chat_history=chat_history_text,
        )

        # ── LLM call: up to 2 Gemini attempts, then instant Cerebras fallback ─
        raw = None
        gemini_quota_hit = False
        for attempt in range(1, 3):          # attempt 1 and 2 only
            try:
                print(f"Invoking Gemini (attempt {attempt})...")
                raw = llm_primary.invoke(formatted_prompt).content
                break                        # success — stop retrying
            except Exception as e:
                err_str = str(e).lower()
                is_quota = (
                    (GeminiResourceExhausted and isinstance(e, GeminiResourceExhausted))
                    or "resourceexhausted" in err_str
                    or "quota" in err_str
                    or "429" in err_str
                )
                if is_quota:
                    print(f"⚠️  Gemini quota hit on attempt {attempt} — switching to Cerebras immediately.")
                    gemini_quota_hit = True
                    break                    # no point retrying quota errors
                if attempt == 2:
                    print(f"Gemini failed twice ({e}). Switching to Cerebras.")
                else:
                    print(f"Gemini attempt {attempt} failed ({e}). Retrying once more...")

        if raw is None or gemini_quota_hit:
            print("Invoking Cerebras (fallback)...")
            raw = llm_backup.invoke(formatted_prompt).content

        data = safe_json_parse(raw)

        # ── Strip em-dashes and double-hyphens from all text fields ──────────
        def clean_dashes(s: str) -> str:
            return s.replace(" — ", " ").replace("—", " ").replace("--", " ").strip()

        definition_text = clean_dashes(data.get("Definition", "Not available"))
        is_fallback = "not available" in definition_text.lower()

        # ── Normalise LLM media (may accidentally come back as a string) ──────
        llm_images = data.get("Image_References", [])
        llm_videos = data.get("Video_References", [])
        if isinstance(llm_images, str):
            llm_images = [llm_images] if llm_images.strip() else []
        if isinstance(llm_videos, str):
            llm_videos = [llm_videos] if llm_videos.strip() else []

        llm_steps = [clean_dashes(s) for s in data.get("Steps", []) if isinstance(s, str)]
        llm_fuqs  = data.get("Follow_Up_Questions", [])
        if not isinstance(llm_fuqs, list):
            llm_fuqs = []
        llm_fuqs = [clean_dashes(q) for q in llm_fuqs if isinstance(q, str) and q.strip()][:3]

        # ── Intent from LLM (drives all branching \u2014 no external classifier) ────
        llm_intent = data.get("Intent", "documentation").strip().lower()
        is_doc = (llm_intent == "documentation")
        print(f"[Intent] {llm_intent!r} | steps={len(llm_steps)} | fuqs={len(llm_fuqs)}")

        # ── Media: regex fallback only for documentation with no LLM media ──
        if is_doc and not llm_images and not llm_videos:
            ctx_images, ctx_videos = extract_media_from_context(context)
            final_images = ctx_images[:3]
            final_videos = ctx_videos[:1]
        else:
            final_images = llm_images
            final_videos = llm_videos

        # ── References only for documentation answers ────────────────────────
        show_refs = is_doc and not is_fallback and bool(context)

        response = AskResponse(
            Definition=definition_text,
            Steps=llm_steps,
            Follow_Up_Questions=llm_fuqs,
            Image_References=final_images,
            Video_References=final_videos,
            References=references_text if show_refs else "",
            Intent=llm_intent,
        )



        # ── MEMORY: persist this Q&A turn ────────────────────────────────────
        # Store a concise summary of the assistant answer (Definition only)
        # so the history stays focused and doesn't inflate the prompt.
        try:
            history.add_user_message(question)
            history.add_ai_message(definition_text)
        except Exception as mem_err:
            print(f"[Memory] Failed to save turn: {mem_err}")
        # ─────────────────────────────────────────────────────────────────────

        return response

    except Exception as e:
        print(f"Error processing answer: {e}")
        return empty_answer()


# -----------------------------
# SESSION DELETE ROUTE
# called by frontend via navigator.sendBeacon on tab/window close
# -----------------------------
@app.post("/session/delete")
def delete_session(req: SessionDeleteRequest):
    if req.api_key != BACKEND_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    safe_id = re.sub(r'[^\w\-]', '_', req.session_id)[:64]
    path = os.path.join(MEMORY_DIR, f"{safe_id}.json")

    if os.path.exists(path):
        try:
            os.remove(path)
            print(f"[Memory] Deleted session file: {path}")
            return {"status": "deleted", "session_id": safe_id}
        except Exception as e:
            print(f"[Memory] Failed to delete {path}: {e}")
            raise HTTPException(status_code=500, detail="Could not delete session")
    else:
        return {"status": "not_found", "session_id": safe_id}