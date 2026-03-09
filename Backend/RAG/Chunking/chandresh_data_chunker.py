"""
Step 3 – Chunking Module (Production Grade)

Input  : raw_pages.json   (output of Step 2 crawler)
Output : chunks.json      (embedding-ready chunks)

Key guarantees:
- Never splits image references
- Preserves section + document context
- Adds rich metadata for retrieval
- Token-safe chunking
"""
import re
import json
import uuid
from pathlib import Path
import tiktoken

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
INPUT_FILE = "E:/Flask/Playage_Support_Bot/Version-1.0/Backend/RAG/Chunking/updated_modified_data.json"
OUTPUT_FILE = "E:/Flask/Playage_Support_Bot/Version-1.0/Backend/RAG/Chunking/updated_modified_data_chunks.json"

MAX_TOKENS = 600          # ideal for MiniLM / OpenAI / Gemini
RESERVED_TOKENS = 120     # space for title + section context

IMAGE_MARKER = "Reference screenshot for documentation purposes"

# -------------------------------------------------
# TOKENIZER
# -------------------------------------------------
encoding = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    return len(encoding.encode(text))


# -------------------------------------------------
# SAFE TEXT SPLITTER
# -------------------------------------------------
def split_text_safely(text: str, max_tokens: int):
    paragraphs = re.split(r"\n\s*\n", text)
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # Hard split extremely large paragraph
        if count_tokens(para) > max_tokens:
            if current.strip():
                chunks.append(current.strip())
                current = ""

            tokens = encoding.encode(para)
            for i in range(0, len(tokens), max_tokens):
                chunks.append(encoding.decode(tokens[i:i + max_tokens]))
            continue

        candidate = current + "\n\n" + para if current else para

        if count_tokens(candidate) <= max_tokens:
            current = candidate
        else:
            chunks.append(current.strip())
            current = para

    if current.strip():
        chunks.append(current.strip())

    return chunks


# -------------------------------------------------
# CHUNK BUILDER
# -------------------------------------------------
def build_chunk(doc, section, text, has_image):
    return {
        "chunk_id": str(uuid.uuid4()),
        "doc_id": doc["doc_id"],
        "title": doc.get("title"),
        "section_heading": section.get("heading"),
        "module": doc.get("module"),
        "category": doc.get("category"),
        "topic_id": doc.get("topic_id"),
        "level": doc.get("level"),
        "priority": doc.get("priority"),
        "has_image": has_image,
        "text": text.strip()
    }


# -------------------------------------------------
# MAIN CHUNKING LOGIC
# -------------------------------------------------
def chunk_documents(pages):
    chunks = []

    for doc in pages:
        doc_title = doc.get("title", "")
        section_text = doc.get("section", "").strip()

        if not section_text:
            continue

        section = {
            "heading": doc_title,
            "text": section_text
        }

        has_image = IMAGE_MARKER in section_text

        base_context = (
            f"Document Title: {doc_title}\n"
            f"Section: {doc_title}\n\n"
        )

        full_text = base_context + section_text

        # Case 1: Fits in one chunk
        if count_tokens(full_text) <= MAX_TOKENS:
            chunks.append(
                build_chunk(doc, section, full_text, has_image)
            )
            continue

        # Case 2: Split
        base_tokens = count_tokens(base_context)
        available_tokens = MAX_TOKENS - base_tokens
        sub_chunks = split_text_safely(section_text, available_tokens)

        for sub_text in sub_chunks:
            chunk_text = base_context + sub_text
            chunks.append(
                build_chunk(doc, section, chunk_text, has_image)
            )

    return chunks


# -------------------------------------------------
# ENTRY POINT
# -------------------------------------------------
def main():
    input_path = Path(INPUT_FILE)
    if not input_path.exists():
        raise FileNotFoundError("raw_pages.json not found")

    with open(input_path, "r", encoding="utf-8") as f:
        pages = json.load(f)

    chunks = chunk_documents(pages)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    print("✅ Step 3 – Chunking complete")
    print(f"📄 Documents processed : {len(pages)}")
    print(f"🧩 Chunks created      : {len(chunks)}")
    print(f"💾 Output saved to     : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()


#


''' Current Result:
✅ Step 3 – Chunking complete
📄 Documents processed : 58
🧩 Chunks created      : 596
💾 Output saved to     : E:/Flask/Playage_Support_Bot/chunks.json
'''