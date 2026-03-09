# 📘 Playage Backoffice RAG API — Developer Documentation

> **File:** `main.py`  
> **Framework:** FastAPI  
> **Version:** 1.0.0  
> **Purpose:** Conversational AI support bot for the Playage Backoffice platform, powered by Retrieval-Augmented Generation (RAG).

---

## 📑 Table of Contents

1. [High-Level Overview](#1-high-level-overview)
2. [System Architecture Diagram](#2-system-architecture-diagram)
3. [Configuration & Environment Variables](#3-configuration--environment-variables)
4. [Application Startup](#4-application-startup)
5. [Request & Response Schemas](#5-request--response-schemas)
6. [End-to-End Request Flow](#6-end-to-end-request-flow)
7. [Memory System (Per-Session Chat History)](#7-memory-system-per-session-chat-history)
8. [RAG Pipeline (Retrieval-Augmented Generation)](#8-rag-pipeline-retrieval-augmented-generation)
9. [Prompt Engineering](#9-prompt-engineering)
10. [LLM Invocation & Fallback Strategy](#10-llm-invocation--fallback-strategy)
11. [Response Post-Processing](#11-response-post-processing)
12. [API Endpoints](#12-api-endpoints)
13. [Helper Functions Reference](#13-helper-functions-reference)
14. [Security](#14-security)
15. [Error Handling](#15-error-handling)
16. [Quick-Start for New Developers](#16-quick-start-for-new-developers)

---

## 1. High-Level Overview

The API is a **FastAPI** application that answers user questions about the Playage Backoffice platform. When a user sends a question, the system:

1. **Authenticates** the request with an API key and checks a rate limit.
2. **Loads the user's chat history** (memory) from disk, keyed by `session_id`.
3. **Retrieves** the most relevant documentation chunks using a **Hybrid RAG** pipeline (FAISS semantic search + BM25 keyword search).
4. **Re-ranks** the retrieved chunks with a Cross-Encoder model for precision.
5. **Builds a prompt** combining: system instructions, chat history, retrieved context, and the user's question.
6. **Calls the primary LLM** (Google Gemini). Falls back to **Cerebras** instantly on quota errors.
7. **Parses and post-processes** the JSON response — cleans text, merges media URLs, applies intent-based rules.
8. **Saves the Q&A turn** back to the session memory file.
9. **Returns a structured JSON response** (`AskResponse`) to the frontend.

---

## 2. System Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND (React)                      │
│  User types question → POST /ask with session_id        │
└──────────────────────────┬──────────────────────────────┘
                           │  HTTP POST /ask
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   FastAPI  (main.py)                     │
│                                                         │
│  ① Rate Limit Check  ──► 429 if exceeded               │
│  ② API Key Auth      ──► 401 if invalid                │
│                                                         │
│  ③ Memory Layer                                         │
│     └─ Load session .json file from /memory_sessions/  │
│     └─ Format last 6 turns as plain text               │
│                                                         │
│  ④ Hybrid RAG Retrieval                                 │
│     ├─ FAISS  (dense vector search, top-12 docs)       │
│     └─ BM25   (sparse keyword search, top-12 docs)     │
│            │                                           │
│            ▼                                           │
│     ⑤ Cross-Encoder Reranker → top-5 docs             │
│            │                                           │
│            ▼                                           │
│     ⑥ Build Context String (≤12,000 chars)            │
│                                                         │
│  ⑦ Prompt Template filled with:                        │
│     context | question | chat_history | username | lang │
│                                                         │
│  ⑧ LLM Call                                            │
│     ├─ Primary:  Google Gemini 2.5 Flash               │
│     │   └─ Up to 2 attempts                            │
│     └─ Fallback: Cerebras gpt-oss-120b (instant)       │
│                                                         │
│  ⑨ Parse & Post-Process JSON response                  │
│     └─ Clean dashes, merge media, apply intent rules   │
│                                                         │
│  ⑩ Save Q&A to memory file                            │
│                                                         │
│  ⑪ Return AskResponse JSON                             │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Frontend   │
                    │  Renders:   │
                    │  Definition │
                    │  Steps      │
                    │  Media URLs │
                    │  References │
                    └─────────────┘
```

---

## 3. Configuration & Environment Variables

All config is loaded from a `.env` file via `python-dotenv`.

| Variable             | Default                                  | Description                                           |
| -------------------- | ---------------------------------------- | ----------------------------------------------------- |
| `INDEX_DIR`          | `…/faq_vector_index`                     | Path to the FAISS vector index directory              |
| `EMBED_MODEL`        | `sentence-transformers/all-MiniLM-L6-v2` | HuggingFace model used to embed documents and queries |
| `GEMINI_API`         | _(required)_                             | Google Gemini API key                                 |
| `CEREBRAS_API_KEY_3` | _(required)_                             | Cerebras API key for fallback LLM                     |
| `FAISS_K`            | `12`                                     | Number of documents FAISS retrieves                   |
| `BM25_K`             | `12`                                     | Number of documents BM25 retrieves                    |
| `RERANK_TOP_N`       | `5`                                      | Number of documents kept after re-ranking             |
| `MAX_CONTEXT_CHARS`  | `12000`                                  | Maximum character budget for context sent to LLM      |
| `MEMORY_TURNS`       | `6`                                      | Number of past Q&A turns included in the prompt       |
| `RATE_LIMIT_RPS`     | `3.0`                                    | Maximum requests per second per IP address            |
| `MEMORY_DIR`         | `memory_sessions`                        | Directory where session `.json` files are stored      |
| `BACKEND_SECRET_KEY` | `playage-bo-secret-2024`                 | Shared secret that every `/ask` request must include  |

> ⚠️ **Important:** Always override `BACKEND_SECRET_KEY` in production via `.env`. Never commit API keys.

---

## 4. Application Startup

The `@app.on_event("startup")` function runs **once** when the server starts. It initialises all the heavy, shared objects as **module-level globals** so they are reused across every request (no re-loading per request).

### What gets loaded at startup:

```
startup()
  ├─ HuggingFaceEmbeddings        ← loads ~90 MB embedding model into RAM
  ├─ FAISS.load_local()           ← loads vector index from disk
  ├─ faiss_retriever              ← wraps vectorstore for document retrieval
  ├─ HybridRetriever              ← combines FAISS + BM25
  ├─ CrossEncoderReranker         ← loads cross-encoder scoring model
  ├─ llm_primary (Gemini 2.5 Flash)
  └─ llm_backup  (Cerebras gpt-oss-120b)
```

If `CEREBRAS_API_KEY` is missing at startup, the server **raises a RuntimeError** and will not start. Missing Gemini key only produces a warning (Cerebras will handle all requests).

---

## 5. Request & Response Schemas

### `AskRequest` — What the frontend sends

```python
{
  "Username":               "JohnDoe",      # Max 30 chars — used in prompt personalisation
  "User_preffered_language":"en",           # "en" or "tr" only (English / Turkish)
  "question":               "How do I add a player?",  # 2–2000 chars
  "top_k":                  5,              # Optional — overrides RERANK_TOP_N (1–20)
  "session_id":             "abc123",       # Optional — links to a persistent memory file
  "api_key":                "playage-bo-secret-2024"  # Mandatory shared secret
}
```

### `AskResponse` — What the API returns

```python
{
  "Intent":             "documentation",   # greeting | conversational | new_user |
                                           # documentation | out_of_scope | clarification_needed
  "Definition":         "Here is how...",  # Main answer text (1 sentence or paragraph)
  "Steps":              ["Step 1…", "Step 2…"],  # Ordered action steps (may be empty)
  "Follow_Up_Questions":["What is…?"],    # Clickable suggestion chips on frontend
  "Image_References":   ["https://…"],    # Image URLs (max 3)
  "Video_References":   ["https://…"],    # Video URLs (max 1)
  "References":         "---\nReferences:\n1. …"  # Doc links shown below answer
}
```

---

## 6. End-to-End Request Flow

This section walks through every line of logic inside the `ask()` endpoint, step by step.

### Step 1 — Rate Limiting

```python
rate_limit(request.client.host)
```

`rate_limit()` maintains an in-memory dictionary (`RATE_BUCKET`) per IP. It counts how many requests arrived from that IP in the **last 1 second**. If the count reaches or exceeds `RATE_LIMIT_RPS` (default 3), it raises an `HTTP 429` before any other work is done.

```
RATE_BUCKET = {
  "192.168.1.1": [1710000001.1, 1710000001.3, 1710000001.7],  # 3 hits this second
  ...
}
```

### Step 2 — API Key Authentication

```python
if req.api_key != BACKEND_API_KEY:
    raise HTTPException(status_code=401, ...)
```

A simple shared-secret check. All `/ask` calls from the frontend must include the same key that is set in the `.env`. This prevents unauthorised use of the API.

### Step 3 — Load Session Memory

```python
session_id = req.session_id or f"anon_{req.Username}"
history    = get_session_history(session_id)
chat_history_text = format_chat_history(history)
```

- If `session_id` is provided by the frontend, that exact session file is used.
- If not, a session is created automatically as `anon_<Username>`.
- `get_session_history()` returns a `FileChatMessageHistory` object backed by a `.json` file at `memory_sessions/<session_id>.json`.
- `format_chat_history()` takes the **last `MEMORY_TURNS × 2` messages** (6 turns = 12 messages) and formats them as readable plain text for injection into the prompt.

```
# Example output of format_chat_history():
User: How do I create a bonus?
Assistant: To create a bonus, navigate to the Bonuses section...
User: Can I set an expiry date?
Assistant: Yes, you can set an expiry date in the bonus configuration panel...
```

### Step 4 — Hybrid RAG Retrieval

```python
docs = hybrid_retriever.search(question + chat_history_text, k_faiss=FAISS_K, k_bm25=BM25_K)
```

The query sent to the retriever is the **user question concatenated with the recent chat history**. This ensures the retriever understands the conversational context (e.g., follow-up questions like "how about that?" are resolved via history).

The `HybridRetriever` internally runs:

- **FAISS** — converts the query to a dense vector using the embedding model and finds the 12 nearest neighbours in the vector index.
- **BM25** — classic keyword matching across all documents, returns top 12.
- Results from both are **merged and deduplicated**.

### Step 5 — Cross-Encoder Re-ranking

```python
reranker.top_n = req.top_k or RERANK_TOP_N
docs = reranker.rerank(question, docs)
```

The merged ~24 candidate documents are passed through a **Cross-Encoder** model (`CrossEncoderReranker`). Unlike the embedding model (which scores docs independently), the cross-encoder takes `(question, document)` pairs and computes a joint relevance score — much more accurate. Only the top `RERANK_TOP_N` (default 5) documents survive.

### Step 6 — Build Context String

```python
context = build_context(docs)
```

`build_context()` iterates over the top-N documents and concatenates them into a single string block with a **character budget** (`MAX_CONTEXT_CHARS = 12,000`). Each document block looks like:

```
Document: Bonus Management
Section: Creating a New Bonus
<page content text here>
```

If adding the next document would exceed the budget, iteration stops. This prevents the prompt from becoming too long and hitting LLM token limits.

### Step 7 — Build Reference Links

```python
for d in docs:
    url = f"https://userguide.playagegaming.tech/en/bo/{doc_id}/"
    ref_list.append(f"{title}\n   {url}")
```

For each reranked document, a user-facing reference link is built using `doc_id` and `title` from the document's metadata. These are assembled into a formatted `References` block that gets attached to the response.

### Step 8 — Fill Prompt Template

```python
formatted_prompt = prompt.format(
    context=context,
    question=question,
    username=req.Username,
    language=req.User_preffered_language,
    current_utc_time=datetime.now(timezone.utc).isoformat(),
    chat_history=chat_history_text,
)
```

The `ChatPromptTemplate` (defined in `build_prompt()`) is filled with all six variables. The LLM receives everything it needs in a single prompt string.

### Step 9 — Call LLM with Fallback

```python
for attempt in range(1, 3):       # Try Gemini twice
    raw = llm_primary.invoke(formatted_prompt).content
    break                          # Success: exit loop

if raw is None or gemini_quota_hit:
    raw = llm_backup.invoke(formatted_prompt).content   # Cerebras
```

See [Section 10](#10-llm-invocation--fallback-strategy) for full detail.

### Step 10 — Parse & Post-Process LLM Response

```python
data = safe_json_parse(raw)
```

The LLM always returns raw JSON. Post-processing then:

- Strips em-dashes and double-hyphens from all text.
- Normalises media lists (LLM might accidentally return a string instead of a list).
- Caps `Follow_Up_Questions` at 3 items.
- Applies **intent-based media logic** (see [Section 11](#11-response-post-processing)).

### Step 11 — Save to Memory

```python
history.add_user_message(question)
history.add_ai_message(definition_text)
```

Only the `Definition` text (not Steps/Media) is stored as the AI message. This keeps memory files compact and the chat history within the prompt concise.

### Step 12 — Return Response

```python
return AskResponse(...)
```

The fully assembled `AskResponse` object is serialised to JSON and returned to the frontend.

---

## 7. Memory System (Per-Session Chat History)

| Component                 | Detail                                                                               |
| ------------------------- | ------------------------------------------------------------------------------------ |
| **Storage**               | Plain JSON files on disk inside `memory_sessions/` folder                            |
| **File naming**           | `{session_id}.json` — special characters sanitised to `_`                            |
| **Library**               | `langchain_community.chat_message_histories.FileChatMessageHistory`                  |
| **Scope**                 | One file per chat session (one browser tab = one session)                            |
| **Cleanup**               | Frontend calls `POST /session/delete` on tab/window close via `navigator.sendBeacon` |
| **Injection into prompt** | Last `MEMORY_TURNS` (6) Q&A pairs, formatted as `User: …\nAssistant: …`              |

### Why store only `Definition` in memory?

Storing the full response (Steps, Media, References) would rapidly bloat the history files and inflate the prompt context. Since the `Definition` contains the key informational content of each answer, it is sufficient for the LLM to maintain conversational coherence.

---

## 8. RAG Pipeline (Retrieval-Augmented Generation)

### Why RAG?

Instead of fine-tuning a model on Playage documentation, RAG allows the LLM to dynamically look up relevant documentation at query time. This means the knowledge base can be updated by simply re-indexing documents, with no model retraining.

### Pipeline Components

```
┌──────────────────────────────────────────────────────┐
│  FAISS Vector Index (faq_vector_index/)              │
│  ├─ Built offline from all Playage docs               │
│  ├─ Each doc chunk stored as a dense vector           │
│  └─ Model: all-MiniLM-L6-v2 (384-dim vectors)        │
└──────────────────┬───────────────────────────────────┘
                   │ FAISS: top-12 by cosine similarity
                   │ BM25:  top-12 by keyword score
                   ▼
        ┌──────────────────────┐
        │  HybridRetriever     │  Merges + deduplicates ~24 docs
        └──────────┬───────────┘
                   ▼
        ┌──────────────────────┐
        │  CrossEncoderReranker│  Scores (query, doc) pairs jointly
        │  → keeps top-5 docs  │  Much more accurate than embedding alone
        └──────────┬───────────┘
                   ▼
        ┌──────────────────────┐
        │  build_context()     │  Concatenates docs within 12,000 char limit
        └──────────────────────┘
```

### Document Metadata

Each document in the FAISS index carries metadata:

| Field          | Example                  | Usage                           |
| -------------- | ------------------------ | ------------------------------- |
| `title`        | `"Bonus Management"`     | Shown in References block       |
| `section`      | `"Creating a New Bonus"` | Shown in context block to LLM   |
| `doc_id`       | `"bonus-management"`     | Used to build the reference URL |
| `page_content` | `"To create a bonus…"`   | Main text sent to LLM           |

---

## 9. Prompt Engineering

The `build_prompt()` function returns a `ChatPromptTemplate`. The template uses `{placeholder}` variables (with `{{` / `}}` for literal braces in the JSON output format).

### Prompt Variables

| Variable             | Source                                   |
| -------------------- | ---------------------------------------- |
| `{username}`         | `req.Username`                           |
| `{language}`         | `req.User_preffered_language`            |
| `{current_utc_time}` | `datetime.now(timezone.utc).isoformat()` |
| `{chat_history}`     | `format_chat_history(history)`           |
| `{context}`          | `build_context(docs)`                    |
| `{question}`         | `req.question.strip()`                   |

### Intent Classification (Inside Prompt)

The LLM itself classifies intent — there is no separate classifier model. The prompt instructs the LLM to output one of 6 intents:

| Intent                 | Trigger                        | Response behaviour                                                 |
| ---------------------- | ------------------------------ | ------------------------------------------------------------------ |
| `greeting`             | "hi", "hello", "hey"           | Friendly 1-sentence welcome. All other fields empty.               |
| `conversational`       | "thanks", "ok", "got it"       | Warm acknowledgement + invite to continue. All other fields empty. |
| `new_user`             | "I'm new", "where do I start?" | Platform overview, 6–7 key areas, 2–3 starter questions.           |
| `documentation`        | Any specific feature question  | Full answer: Definition, Steps, Media, References.                 |
| `out_of_scope`         | Unrelated to Playage           | Polite scope explanation. All other fields empty.                  |
| `clarification_needed` | Too vague                      | Specific clarifying question. All other fields empty.              |

### Language Detection (Inside Prompt)

The LLM is prompted to detect the **actual writing language** of the user's message and mirror it — regardless of `User_preffered_language`. This means:

- A user with `language=en` who writes in Turkish → gets a Turkish response.
- All 6 output fields are affected (Definition, Steps, Follow_Up_Questions).

---

## 10. LLM Invocation & Fallback Strategy

```
Attempt 1: Gemini 2.5 Flash
    ├─ Success → use response
    └─ Quota/Rate error (429, ResourceExhausted) → immediately switch to Cerebras
    └─ Other error → retry once (Attempt 2)

Attempt 2: Gemini 2.5 Flash
    ├─ Success → use response
    └─ Any error → switch to Cerebras

Cerebras (gpt-oss-120b):
    └─ Called if Gemini fails or hits quota on either attempt
```

### Why two LLMs?

- **Gemini 2.5 Flash** is the primary because it has strong instruction-following, multilingual capability, and fast response times.
- **Cerebras** (via an OpenAI-compatible endpoint) is the fallback for quota exhaustion. It is configured with `response_format: json_object` to guarantee valid JSON output even without the strict prompt formatting that Gemini honours naturally.

### LLM Configuration

| Setting     | Gemini                            | Cerebras                       |
| ----------- | --------------------------------- | ------------------------------ |
| Model       | `gemini-2.5-flash`                | `gpt-oss-120b`                 |
| Temperature | `0.2`                             | `0.2`                          |
| Max retries | `0` (disabled — handled manually) | LangChain default              |
| JSON mode   | Via prompt instruction            | `response_format: json_object` |

---

## 11. Response Post-Processing

After `safe_json_parse(raw)` returns a Python dict, several cleaning steps are applied:

### 11.1 — Em-dash Cleaning

```python
def clean_dashes(s: str) -> str:
    return s.replace(" — ", " ").replace("—", " ").replace("--", " ").strip()
```

LLMs frequently output em-dashes (`—`) as stylistic punctuation. This is stripped to keep the UI clean.

### 11.2 — Media URL Normalisation

```python
if isinstance(llm_images, str):
    llm_images = [llm_images] if llm_images.strip() else []
```

The LLM is instructed to return lists but occasionally returns a single URL string. This guard converts it to a proper list.

### 11.3 — Intent-Based Media Fallback

```python
if is_doc and not llm_images and not llm_videos:
    ctx_images, ctx_videos = extract_media_from_context(context)
    final_images = ctx_images[:3]
    final_videos = ctx_videos[:1]
else:
    final_images = llm_images
    final_videos = llm_videos
```

If the intent is `documentation` but the LLM returned no media URLs, the API falls back to **regex extraction** from the raw context string. This ensures images/videos embedded in the documentation are surfaced even when the LLM misses them.

Regex patterns used:

- **Images:** `https?://\S+\.(webp|png|jpg|jpeg|gif)`
- **Videos:** `https?://\S+\.(mp4|webm|ogg|mov)`

### 11.4 — References Guard

```python
show_refs = is_doc and not is_fallback and bool(context)
```

References are only shown when:

- Intent is `documentation`.
- The answer is **not** a "not available" fallback.
- Context was non-empty (i.e., something was actually retrieved).

---

## 12. API Endpoints

### `POST /ask`

Main question-answering endpoint.

| Field      | Value                           |
| ---------- | ------------------------------- |
| Method     | `POST`                          |
| URL        | `/ask`                          |
| Auth       | `api_key` field in request body |
| Rate limit | 3 requests/second per IP        |

**Request body:** `AskRequest` (see [Section 5](#5-request--response-schemas))  
**Response:** `AskResponse` (see [Section 5](#5-request--response-schemas))

**Error codes:**

| Code  | Reason                                                         |
| ----- | -------------------------------------------------------------- |
| `400` | Empty question after stripping whitespace                      |
| `401` | Invalid or missing `api_key`                                   |
| `429` | Rate limit exceeded                                            |
| `500` | Unhandled internal error (returns `empty_answer()` gracefully) |

---

### `POST /session/delete`

Deletes the session memory file for a given `session_id`. Called automatically by the frontend when the user closes the tab.

**Request body:**

```json
{
  "session_id": "abc123",
  "api_key": "playage-bo-secret-2024"
}
```

**Response:**

```json
{ "status": "deleted", "session_id": "abc123" }
// or
{ "status": "not_found", "session_id": "abc123" }
```

---

## 13. Helper Functions Reference

| Function                              | Location | Purpose                                                        |
| ------------------------------------- | -------- | -------------------------------------------------------------- |
| `build_prompt()`                      | Line 100 | Returns the `ChatPromptTemplate` with all instructions         |
| `startup()`                           | Line 221 | Loads all heavy globals on server start                        |
| `rate_limit(ip)`                      | Line 271 | Enforces per-IP request rate limit (429 on breach)             |
| `safe_json_parse(s)`                  | Line 282 | Parses LLM output; strips accidental markdown fences           |
| `get_session_history(session_id)`     | Line 294 | Returns/creates a `FileChatMessageHistory` for the session     |
| `format_chat_history(history)`        | Line 301 | Formats last N turns as `User: …\nAssistant: …`                |
| `extract_media_from_context(context)` | Line 322 | Regex-extracts image & video URLs from context string          |
| `merge_dedup(llm_list, context_list)` | Line 329 | Merges two URL lists without duplicates, LLM items first       |
| `empty_answer()`                      | Line 341 | Returns a safe fallback `AskResponse` on error                 |
| `build_context(docs)`                 | Line 353 | Concatenates top docs into a context string within char budget |

---

## 14. Security

| Mechanism                   | Implementation                                                                                          |
| --------------------------- | ------------------------------------------------------------------------------------------------------- |
| **API Key Auth**            | Every `/ask` and `/session/delete` request must include `api_key` matching `BACKEND_SECRET_KEY`         |
| **Rate Limiting**           | In-memory per-IP bucket; max 3 req/sec by default                                                       |
| **Input Validation**        | Pydantic `AskRequest` enforces field lengths, language enum (`en`/`tr`), question length (2–2000 chars) |
| **Session ID Sanitisation** | `re.sub(r'[^\w\-]', '_', session_id)[:64]` — prevents path traversal in file names                      |
| **CORS**                    | Configured with `allow_origins=["*"]` — **restrict this in production**                                 |

> ⚠️ **Production Note:** Change `allow_origins=["*"]` to your frontend domain before going live. Also rotate `BACKEND_SECRET_KEY` and ensure it is only in `.env` (never committed to git).

---

## 15. Error Handling

| Scenario                              | Behaviour                                                          |
| ------------------------------------- | ------------------------------------------------------------------ |
| Missing `CEREBRAS_API_KEY` at startup | Server refuses to start (`RuntimeError`)                           |
| Missing `GEMINI_API_KEY` at startup   | Warning logged; Cerebras handles all requests                      |
| Gemini quota/rate error               | Instant Cerebras fallback (no wait/retry)                          |
| Gemini other error on attempt 1       | Retry once (attempt 2)                                             |
| Gemini fails both attempts            | Cerebras fallback                                                  |
| LLM returns invalid JSON              | `safe_json_parse` raises → outer `except` returns `empty_answer()` |
| Memory file save failure              | Logged but **not fatal** — response still returned                 |
| Session file not found on delete      | Returns `{"status": "not_found"}`, no error                        |

---

## 16. Quick-Start for New Developers

### 1. Set Up Environment

```bash
# Copy and fill the .env file
cp .env.example .env
# Set GEMINI_API, CEREBRAS_API_KEY_3, BACKEND_SECRET_KEY, INDEX_DIR
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the Server

```bash
uvicorn main:app --reload
```

The server will print `✅ API Ready` once all models are loaded (may take 10–20 seconds on first run due to model downloads).

### 4. Test with cURL

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "Username": "DevTest",
    "User_preffered_language": "en",
    "question": "How do I add a new player?",
    "session_id": "dev-test-001",
    "api_key": "playage-bo-secret-2024"
  }'
```

### 5. Understanding the Codebase (Reading Order)

For a new developer, read the code in this order:

1. **Configuration block** (lines 32–55) — understand what can be tuned.
2. **Schemas** (lines 73–94) — understand what goes in / comes out.
3. **`build_prompt()`** (lines 100–206) — this is the "brain" of the bot.
4. **`startup()`** (lines 220–265) — understand what gets loaded and why.
5. **`ask()` endpoint** (lines 382–532) — the main request handler (follow the steps in [Section 6](#6-end-to-end-request-flow)).
6. **Helper functions** (lines 271–376) — details of each utility.
7. **`/session/delete`** (lines 539–556) — simple cleanup endpoint.

### 6. Key Files Alongside `main.py`

| File                              | Purpose                                                     |
| --------------------------------- | ----------------------------------------------------------- |
| `hybrid_retriever.py`             | `HybridRetriever` class — combines FAISS + BM25             |
| `reranker.py`                     | `CrossEncoderReranker` class — re-scores document relevance |
| `memory_sessions/*.json`          | Per-session chat history files (auto-created)               |
| `RAG/Embedding/faq_vector_index/` | Pre-built FAISS index of all Playage docs                   |
| `.env`                            | All secret keys and tunable parameters                      |

---

_Documentation generated for `main.py` v1.0.0 — Playage Backoffice Support Bot_
