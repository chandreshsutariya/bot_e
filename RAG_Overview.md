Playage Backoffice RAG System

Enterprise Hybrid Retrieval + Reranked + FastAPI Deployment

1️⃣ Project Overview

This project implements a production-grade Retrieval-Augmented Generation (RAG) system for Playage Backoffice documentation.

It allows users to:

Ask documentation-related questions

Get structured answers (Definition + Steps + Tips)

Retrieve relevant screenshots

Avoid hallucinated content

Receive safe fallback responses

The system uses:

Hybrid retrieval (Dense + Sparse)

Cross-encoder reranking

Strict context-only prompting

JSON-only structured output

FastAPI production API layer

2️⃣ System Architecture
User
↓
FastAPI Endpoint (/ask)
↓
Intent Router (Greeting / Short Query / RAG)
↓
Hybrid Retrieval (FAISS + BM25)
↓
Cross-Encoder Reranker
↓
Context Builder (Token Safe)
↓
Gemini LLM (Strict Prompt)
↓
JSON Validation
↓
Final Response
3️⃣ Roadmap – What We Built Step-by-Step
✅ Step 1 – Sitemap Parsing & Metadata Extraction

Goal: Build structured document index.

What we did:

Parsed sitemap XML

Extracted:

doc_id

url

category

topic_id

module

lastmod

Created documents_index.json

Technologies:

BeautifulSoup

XML parsing

JSON serialization

✅ Step 2 – Web Crawler & Cleaner

Goal: Extract clean structured documentation.

Features:

Used readability-lxml

Extracted:

Headings

Paragraphs

Lists

Images

Injected image URLs into text

Removed:

Footer boilerplate

Duplicate lines

Confidential banners

Fixed encoding issues using ftfy

Output:
raw_pages.json

Each page contains:

title
sections[]
heading
text
✅ Step 3 – Chunking Strategy

Goal: Create semantically strong chunks.

Strategy:

Section-based chunking (not arbitrary)

Preserved:

title

section

category

topic_id

has_image flag

Used RecursiveCharacterTextSplitter

Result:
chunks.json

596+ structured chunks.

✅ Step 4 – FAISS Embedding Index

Goal: Dense vector retrieval.

Model Used:
sentence-transformers/all-MiniLM-L6-v2
Vector Store:

FAISS

Local index storage

Result:
faq_vector_index/

Dense semantic search enabled.

✅ Step 5 – Hybrid Retrieval (Major Upgrade)
Problem:

Dense search alone misses keyword-heavy queries.

Solution:

Hybrid Search:

FAISS (semantic)

BM25 (lexical sparse)

Implementation:

Custom HybridRetriever

HybridRetriever(
faiss_retriever,
documents
)

Improves recall dramatically.

✅ Step 6 – Cross-Encoder Reranker (Precision Boost)
Model Used:
cross-encoder/ms-marco-MiniLM-L-6-v2
Why?

Embeddings ≠ precision

Cross-encoder scores query-document pair directly

Flow:

Retrieve top 12 → Rerank → Keep top 5

Result:
Much higher answer accuracy.

✅ Step 7 – Strict Prompt Engineering
Design Goals:

Zero hallucination

Context-only answers

Structured JSON

No external knowledge

No system leakage

Output Format:
{
"Definition": "",
"Steps": [],
"Tips": [],
"Image_References": ""
}
Protections:

Strict fallback message

No markdown

No extra keys

JSON-only enforcement

✅ Step 8 – Hallucination Guarding

We added:

Retrieval fallback (no docs → empty response)

Context size cap (avoid truncation)

JSON parsing validation

Safe fallback if JSON invalid

Greeting router (skip RAG for "Hi")

This makes it production-safe.

✅ Step 9 – FastAPI Production Layer
Endpoint:
POST /ask
Features:

Rate limiting

JSON validation

Context bounding

Reranking

Hybrid retrieval

Structured response

Additional:
GET /health
POST /ask_debug
4️⃣ Technologies Used
Retrieval Layer

FAISS

rank-bm25

sentence-transformers

Reranking

cross-encoder/ms-marco-MiniLM-L-6-v2

LLM

Gemini 2.5 Flash

Strict JSON output

Low temperature (0.2)

API Layer

FastAPI

Pydantic

Uvicorn

Data Processing

BeautifulSoup

readability-lxml

ftfy

5️⃣ Hallucination Prevention Strategy
Risk Protection
Out-of-context answers Strict prompt rule
Empty retrieval Safe fallback
Large context MAX_CONTEXT_CHARS cap
Broken JSON JSON validation
Greeting noise Intent router
Over-retrieval Reranker
External knowledge leakage Hard rule in prompt
6️⃣ Final System Characteristics

Enterprise-grade RAG

Hybrid semantic + lexical search

Cross-encoder precision boost

Context-safe generation

JSON-structured UI-ready answers

Production API

Rate limiting

Greeting routing

Fully grounded answers

7️⃣ Current Limitations

No multi-turn memory

No confidence score returned

No authentication on API

No analytics dashboard

8️⃣ Future Improvements Roadmap
Phase 2

Add answer confidence score

Add citation list (doc_id + section)

Add Redis-based rate limiting

Add API key authentication

Phase 3

Add conversation memory

Add feedback loop (thumbs up/down)

Add logging analytics

Add monitoring (Prometheus)

Phase 4

Multi-index routing

Multi-language support

Async batching

Load balancing

9️⃣ Deployment Guide
Run locally:
uvicorn main:app --host 0.0.0.0 --port 8000
Production:
uvicorn main:app --workers 2 --host 0.0.0.0 --port 8000
Recommended:

Use Nginx reverse proxy

Add HTTPS

Add API authentication

Add Redis rate limiting

🔟 Final Summary

You have built:

Hybrid Retrieval RAG

Cross-Encoder Reranked System

Strict Hallucination Guarded Prompt

Production FastAPI API

Enterprise-Structured JSON Output

This is not a basic chatbot.

This is a real enterprise documentation assistant system.
