# Playage Support Bot – How It Works (A Simple Guide)

Welcome! This document explains how the "brain" (backend) of the Playage Support Bot works. Even if you don't write code, this guide will help you understand what happens behind the scenes when a user asks a question.

---

## 🏗️ 1. The Big Picture

The Playage Support Bot uses a modern AI technique called **RAG** (Retrieval-Augmented Generation). 
Think of it like an open-book exam:
1. **The Question:** The user asks a question.
2. **The Open Book (Retrieval):** The bot searches through our official Playage documentation to find the exact paragraphs that contain the answer.
3. **The Answer (Generation):** The AI reads those specific paragraphs and writes a helpful, formatted response for the user.

Why do it this way? Because it prevents the AI from "hallucinating" or making things up. It can only answer based on our official manuals!

---

## 🚦 2. Step-by-Step: The Journey of a Message

When a user types a message and hits send, here is everything our system does in the blink of an eye:

### Step A: Security First 🛡️
Before even reading the message, the system checks the ID card (API Key) of the request. 
- If someone tries to guess the password and fails too many times, their IP address is temporarily banned. 
- The system also checks if the user is sending messages way too fast (Rate Limiting).
- Finally, it "cleans" the text to make sure there are no hidden malicious codes (Prompt Injection).

### Step B: The "Intent Gate" (Is this a real question?) 🚪
Not every message needs a deep search through the manuals. 
If the user just says `"hello"`, `"okay"`, or `"thanks"`, there's no need to waste time searching the manuals. 
- Our system uses a **Fast Checker** to catch greetings and simple words instantly.
- If it's just a greeting, it skips the search completely. This makes the bot much faster and cheaper to run!

### Step C: The "Smart" Search (3 Stages) 🧠
If the message *is* a real question, the bot needs to find the answer. It does this in 3 smart stages:

1. **Condensing the Question:**
   Let's say the user asked: "How do I add a player?" and then asks "Can I delete them?".
   The bot uses AI to rewrite the second question so it makes sense on its own: *"Can I delete a player in Playage Backoffice?"*
2. **Searching (Pass 1):**
   It searches our manuals using the rewritten question. It gives the results a "Confidence Score" (from 0 to 1). If the score is high enough (above our threshold), it stops here! It found the answer.
3. **Fallback Search (Pass 2):**
   If the first search had a *low* confidence score, the bot doesn't give up. It uses AI to invent an *alternative* way to ask the question (using different keywords), and searches again. It combines the best results from both searches.

### Step D: Reading and Answering 📖
Now the system has the best paragraphs from our manuals. It hands these paragraphs, along with the user's question, to our primary AI (Google Gemini).
Gemini reads the paragraphs and writes a beautiful response. It structures the answer into:
- A clear definition/explanation.
- Step-by-step instructions.
- Follow-up questions the user might want to ask next.
- Images or Videos to help explain.

*Note: If Google Gemini is too busy or crashes, the system instantly switches to a backup AI (Cerebras) so the user never sees an error!*

### Step E: Remembering for Next Time 📝
Finally, the system saves a short summary of what was just talked about into a memory file. This way, if the user asks a follow-up question later, the bot remembers the context of the conversation.

---

## ⚙️ 3. The Key Ingredients (Tools We Use)

Here are the main tools that make this system work:

* **FastAPI:** The engine that runs our server. It receives the messages from the internet and sends the answers back.
* **FAISS & BM25:** Our search engines. FAISS searches based on "meaning" (like understanding synonyms), while BM25 searches based on exact keyword matches. Together, they find the best documents.
* **CrossEncoder (Reranker):** The judge. After the search engines find potential answers, the CrossEncoder grades them on how perfectly they match the user's question.
* **Google Gemini (Primary AI):** The main brain that reads the manuals and writes the final responses.
* **Cerebras (Backup & Fast AI):** A super-fast, secondary brain. We use it for the quick tasks (like rewriting the questions in Step C) and as a backup if Gemini is down.

---

## 🔒 4. Safety & Limitations

* **No Hallucinations:** If the bot cannot find the answer in the official documents, it is programmed to admit it doesn't know, rather than making up a fake answer.
* **Memory Limits:** The bot only remembers the last few messages of a conversation. If a user talks for hours, it will slowly forget the very beginning of the chat to keep things fast.
* **Automatic Cleanup:** When a user closes their browser tab, a signal is sent to the server to delete their chat memory file, keeping our systems clean and secure.
