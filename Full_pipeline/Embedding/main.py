"""
FAISS Embedding Pipeline
━━━━━━━━━━━━━━━━━━━━━━━━
Takes any *_rag.json produced by data_fetcher.py and builds a
FAISS vector index saved as  <sitename>_faiss_index/

Usage:
    python faiss_builder.py oppiwallet_com_rag.json
    python faiss_builder.py oppiwallet_com_rag.json --model all-mpnet-base-v2
    python faiss_builder.py oppiwallet_com_rag.json --out my_index
    python faiss_builder.py oppiwallet_com_rag.json --batch 64
"""
import os, warnings
os.environ["TF_ENABLE_ONEDNN_OPTS"]  = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"]   = "3"
os.environ["TRANSFORMERS_NO_TF"]     = "1"     # force HF to use torch only
os.environ["USE_TF"]                 = "0"
os.environ["USE_TORCH"]              = "1"
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)



import json
import argparse
import re
import time
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime, timezone
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings


# ══════════════════════════════════════════════════════════════
#  AVAILABLE MODELS  (pass short alias via --model)
# ══════════════════════════════════════════════════════════════

MODELS = {
    # fast & light  (default)
    "minilm":    "sentence-transformers/all-MiniLM-L6-v2",
    # best quality
    "mpnet":     "sentence-transformers/all-mpnet-base-v2",
    # multilingual
    "multilingual": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    # pass full HF model name directly too
}

DEFAULT_MODEL = "minilm"


# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════

def _banner(msg: str):
    print(f"\n{'═'*55}")
    print(f"  {msg}")
    print(f"{'═'*55}")


def _step(n: int, total: int, msg: str):
    print(f"\n[{n}/{total}] {msg} …")


def stem_from_rag_file(path: str) -> str:
    """oppiwallet_com_rag.json  →  oppiwallet_com"""
    name = Path(path).stem                       # oppiwallet_com_rag
    name = re.sub(r'_rag$', '', name)            # oppiwallet_com
    return name or "site"


def stem_from_url(url: str) -> str:
    hostname = urlparse(url).hostname or "site"
    return re.sub(r'[^a-zA-Z0-9]', '_', hostname)


def resolve_model_name(alias: str) -> str:
    return MODELS.get(alias.lower(), alias)      # fallback = treat as full HF name


# ══════════════════════════════════════════════════════════════
#  STEP 1 — LOAD RAG JSON
# ══════════════════════════════════════════════════════════════

def load_rag_json(path: str) -> tuple[list[dict], dict]:
    """
    Accepts two formats:
      A) { "meta": {...}, "chunks": [...] }   ← data_fetcher.py output
      B) [chunk, chunk, ...]                  ← raw list
    Returns (chunks_list, meta_dict)
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data, {}

    if isinstance(data, dict):
        # handle both "chunks" and flat root keys
        if "chunks" in data:
            return data["chunks"], data.get("meta", {})
        # legacy: some pipelines store chunks at top level with other keys mixed in
        chunks = [v for v in data.values() if isinstance(v, list)]
        if chunks:
            return chunks[0], {}

    raise ValueError(f"Unrecognised RAG JSON format in {path}")


# ══════════════════════════════════════════════════════════════
#  STEP 2 — VALIDATE & CLEAN CHUNKS
# ══════════════════════════════════════════════════════════════

def validate_chunks(chunks: list[dict]) -> tuple[list[dict], list[str]]:
    """Drop chunks with empty text; report issues."""
    valid:  list[dict] = []
    issues: list[str]  = []

    for i, chunk in enumerate(chunks):
        text = (chunk.get("text") or "").strip()
        if not text:
            issues.append(f"Chunk [{i}] skipped — empty text (chunk_id={chunk.get('chunk_id', '?')})")
            continue
        valid.append(chunk)

    return valid, issues


# ══════════════════════════════════════════════════════════════
#  STEP 3 — CONVERT TO LANGCHAIN DOCUMENTS
# ══════════════════════════════════════════════════════════════

# All metadata keys we carry over (None values are safely dropped)
_META_KEYS = [
    "chunk_id", "doc_id", "url", "title", "heading",
    "char_count", "token_est", "source",
    # legacy / optional keys (from documents_index pipelines)
    "section_heading", "module", "category",
    "topic_id", "level", "priority", "has_image",
]


def to_langchain_docs(chunks: list[dict]) -> list[Document]:
    docs: list[Document] = []
    for chunk in chunks:
        metadata = {
            k: chunk[k]
            for k in _META_KEYS
            if chunk.get(k) is not None
        }
        docs.append(Document(
            page_content=chunk["text"].strip(),
            metadata=metadata,
        ))
    return docs


# ══════════════════════════════════════════════════════════════
#  STEP 4 — BUILD & SAVE FAISS INDEX
# ══════════════════════════════════════════════════════════════

def build_and_save(
    documents:   list[Document],
    index_dir:   str,
    model_name:  str,
    batch_size:  int = 32,
) -> dict:
    """
    Embed documents in batches and save FAISS index.
    Returns timing/stats dict.
    """
    print(f"     Model   : {model_name}")
    print(f"     Docs    : {len(documents)}")
    print(f"     Batch   : {batch_size}")

    t0 = time.time()

    embeddings = HuggingFaceEmbeddings(
        model_name=model_name,
        encode_kwargs={"batch_size": batch_size},
    )

    print(f"     ✓  Model loaded  ({time.time()-t0:.1f}s)")

    t1 = time.time()

    # Build FAISS index in one call (LangChain handles batching internally)
    vectorstore = FAISS.from_documents(documents, embeddings)

    embed_time = time.time() - t1
    print(f"     ✓  Embeddings done  ({embed_time:.1f}s, ~{embed_time/len(documents)*1000:.1f}ms/doc)")

    # Save
    Path(index_dir).mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(index_dir)

    total_time = time.time() - t0
    return {
        "index_dir":   index_dir,
        "docs_indexed": len(documents),
        "embed_time_s": round(embed_time, 2),
        "total_time_s": round(total_time, 2),
        "model":        model_name,
    }


# ══════════════════════════════════════════════════════════════
#  STEP 5 — SAVE MANIFEST
# ══════════════════════════════════════════════════════════════

def save_manifest(index_dir: str, meta: dict, stats: dict, issues: list[str]):
    """Write index_manifest.json next to the FAISS files for traceability."""
    manifest = {
        "generated_at":  datetime.now(timezone.utc).isoformat(),
        "index_dir":     index_dir,
        "model":         stats["model"],
        "docs_indexed":  stats["docs_indexed"],
        "embed_time_s":  stats["embed_time_s"],
        "total_time_s":  stats["total_time_s"],
        "source_meta":   meta,
        "skipped_chunks": issues,
    }
    out = Path(index_dir) / "index_manifest.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"     ✓  Manifest saved → {out}")


# ══════════════════════════════════════════════════════════════
#  MAIN PIPELINE
# ══════════════════════════════════════════════════════════════

def run(
    rag_json:   str,
    model:      str = DEFAULT_MODEL,
    out_dir:    str = "",
    batch_size: int = 32,
) -> dict:
    timestamp = datetime.now(timezone.utc).isoformat()

    # ── Resolve paths & names ────────────────────────────────
    rag_path = Path(rag_json)
    if not rag_path.exists():
        raise FileNotFoundError(f"RAG JSON not found: {rag_json}")

    stem       = stem_from_rag_file(rag_json)
    index_dir  = out_dir or f"{stem}_faiss_index"
    model_name = resolve_model_name(model)

    _banner(f"FAISS Embedding Pipeline\n  Input  : {rag_path.name}\n  Output : {index_dir}/")

    # ── Load ─────────────────────────────────────────────────
    _step(1, 5, "Loading RAG JSON")
    chunks, meta = load_rag_json(rag_json)
    print(f"     ✓  {len(chunks)} chunks loaded")

    if meta.get("base_url"):
        print(f"     ✓  Source : {meta['base_url']}")

    # ── Validate ─────────────────────────────────────────────
    _step(2, 5, "Validating chunks")
    valid_chunks, issues = validate_chunks(chunks)
    print(f"     ✓  {len(valid_chunks)} valid  |  {len(issues)} skipped")
    for issue in issues[:5]:                      # show max 5 warnings
        print(f"     ⚠  {issue}")
    if len(issues) > 5:
        print(f"     ⚠  … and {len(issues)-5} more (see manifest)")

    if not valid_chunks:
        raise ValueError("No valid chunks to embed. Check your RAG JSON.")

    # ── Convert ───────────────────────────────────────────────
    _step(3, 5, "Converting to LangChain Documents")
    documents = to_langchain_docs(valid_chunks)
    print(f"     ✓  {len(documents)} documents ready")

    # ── Embed & index ─────────────────────────────────────────
    _step(4, 5, "Embedding & building FAISS index")
    stats = build_and_save(documents, index_dir, model_name, batch_size)

    # ── Manifest ──────────────────────────────────────────────
    _step(5, 5, "Saving manifest")
    save_manifest(index_dir, meta, stats, issues)

    _banner(
        f"Status   : SUCCESS\n"
        f"  Indexed  : {stats['docs_indexed']} documents\n"
        f"  Model    : {model_name}\n"
        f"  Time     : {stats['total_time_s']}s\n"
        f"  Saved at : {index_dir}/"
    )

    return {
        "status":    "success",
        "index_dir": index_dir,
        "stats":     stats,
        "issues":    issues,
    }


# ══════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(
        description="Build FAISS vector index from a RAG JSON file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Model aliases:
  minilm        sentence-transformers/all-MiniLM-L6-v2       (default, fast)
  mpnet         sentence-transformers/all-mpnet-base-v2       (best quality)
  multilingual  sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

Examples:
  python faiss_builder.py oppiwallet_com_rag.json
  python faiss_builder.py oppiwallet_com_rag.json --model mpnet
  python faiss_builder.py oppiwallet_com_rag.json --out custom_index
  python faiss_builder.py oppiwallet_com_rag.json --batch 64
        """
    )
    ap.add_argument("rag_json",
                    help="Path to *_rag.json produced by data_fetcher.py")
    ap.add_argument("--model",  default=DEFAULT_MODEL,
                    help="Embedding model alias or full HuggingFace name (default: minilm)")
    ap.add_argument("--out",    default="",
                    help="Custom output folder name (default: <sitename>_faiss_index)")
    ap.add_argument("--batch",  type=int, default=32,
                    help="Embedding batch size (default: 32)")
    args = ap.parse_args()

    run(
        rag_json   = args.rag_json,
        model      = args.model,
        out_dir    = args.out,
        batch_size = args.batch,
    )


if __name__ == "__main__":
    main()