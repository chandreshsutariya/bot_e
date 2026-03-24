"""
Data Fetcher — Full RAG Pipeline
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
One command does everything:
  URL → sanitize → sitemap → scrape → RAG chunks → sitename_rag.json

Usage:
    python data_fetcher.py oppiwallet.com
    python data_fetcher.py https://example.com --delay 2 --limit 50
    python data_fetcher.py example.com --no-save
"""

import xml.etree.ElementTree as ET
import argparse
import hashlib
import json
import re
import time
import requests
from bs4 import BeautifulSoup
from readability import Document
from urllib.parse import urljoin, urlparse
from datetime import datetime, timezone

try:
    import ftfy
    HAS_FTFY = True
except ImportError:
    HAS_FTFY = False


# ══════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

SITEMAP_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap/sitemap.xml",
    "/sitemap1.xml",
    "/page-sitemap.xml",
    "/post-sitemap.xml",
]

BLACKLIST_PHRASES = [
    "Confidential Document",
    "Enterprise Management System",
    "For Authorized Personnel Only",
]


# ══════════════════════════════════════════════════════════════
#  STEP 1 — URL SANITIZER
# ══════════════════════════════════════════════════════════════

def sanitize_url(raw: str) -> str:
    """
    Accept any format and return a clean https base URL.

    oppiwallet.com            → https://oppiwallet.com
    www.oppiwallet.com        → https://www.oppiwallet.com
    http://oppiwallet.com/p   → https://oppiwallet.com
    HTTPS://OPPIWALLET.COM    → https://oppiwallet.com
    """
    raw = raw.strip().strip("'\"")
    if not re.match(r'^https?://', raw, re.IGNORECASE):
        raw = "https://" + raw

    parsed   = urlparse(raw)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    port     = parsed.port

    if not hostname:
        raise ValueError(f"Cannot parse hostname from: {raw!r}")

    base = f"https://{hostname}"
    if port and port not in (80, 443):
        base += f":{port}"
    return base


def hostname_stem(url: str) -> str:
    hostname = urlparse(url).hostname or "site"
    return re.sub(r'[^a-zA-Z0-9]', '_', hostname)


# ══════════════════════════════════════════════════════════════
#  STEP 2 — SITEMAP DISCOVERY
# ══════════════════════════════════════════════════════════════

def http_get(url: str, timeout: int = 15):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            return r
    except Exception:
        pass
    return None


def find_sitemap_url(base: str):
    r = http_get(f"{base}/robots.txt")
    if r:
        for line in r.text.splitlines():
            if line.lower().startswith("sitemap:"):
                return line.split(":", 1)[1].strip()
    for path in SITEMAP_PATHS:
        url = base.rstrip("/") + path
        r = http_get(url)
        if r and ("<urlset" in r.text or "<sitemapindex" in r.text):
            return url
    return None


def parse_sitemap(url: str, collected: list, visited: set, errors: list):
    if url in visited:
        return
    visited.add(url)

    r = http_get(url)
    if not r:
        errors.append(f"Could not fetch sitemap: {url}")
        return

    try:
        root = ET.fromstring(r.content)
    except ET.ParseError as e:
        errors.append(f"XML parse error at {url}: {e}")
        return

    tag = root.tag.lower()
    ns  = "{http://www.sitemaps.org/schemas/sitemap/0.9}loc"

    if "sitemapindex" in tag:
        for child in [loc.text.strip() for loc in root.iter(ns) if loc.text]:
            parse_sitemap(child, collected, visited, errors)
    elif "urlset" in tag:
        collected.extend([loc.text.strip() for loc in root.iter(ns) if loc.text])


def get_sitemap_urls(base: str, errors: list):
    sitemap_url = find_sitemap_url(base)
    if not sitemap_url:
        return None, []

    raw: list[str] = []
    parse_sitemap(sitemap_url, raw, set(), errors)

    seen:   set[str]  = set()
    unique: list[str] = []
    for u in raw:
        if u not in seen:
            seen.add(u)
            unique.append(u)

    return sitemap_url, unique


# ══════════════════════════════════════════════════════════════
#  STEP 3 — CONTENT EXTRACTION
# ══════════════════════════════════════════════════════════════

def fix_encoding(text: str) -> str:
    return ftfy.fix_text(text) if HAS_FTFY else text


def normalize_text(text: str) -> str:
    text = fix_encoding(text)
    # deduplicate lines
    seen: set[str] = set()
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if s and s not in seen:
            seen.add(s)
            lines.append(s)
    text = "\n".join(lines)
    # remove boilerplate
    for phrase in BLACKLIST_PHRASES:
        text = text.replace(phrase, "")
    # remove footer pattern
    cleaned = []
    for line in text.splitlines():
        low = line.lower()
        if not ("professional documentation" in low and "version" in low):
            cleaned.append(line)
    return "\n".join(cleaned).strip()


def extract_page(html: str, base_url: str) -> dict:
    doc        = Document(html)
    clean_html = doc.summary(html_partial=True)
    soup       = BeautifulSoup(clean_html, "html.parser")

    # Title
    title = ""
    if soup.title and soup.title.text:
        title = fix_encoding(soup.title.text.strip())
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = fix_encoding(h1.get_text(strip=True))
    if not title:
        title = doc.title()

    # Sections
    sections: list[dict] = []
    current = {"heading": "Introduction", "text": ""}

    for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "img", "video"]):
        if tag.name.startswith("h"):
            if current["text"].strip():
                current["text"] = normalize_text(current["text"])
                sections.append(current)
            current = {"heading": fix_encoding(tag.get_text(strip=True)), "text": ""}

        elif tag.name == "img":
            src = tag.get("src") or tag.get("data-src") or tag.get("data-lazy-src")
            if src:
                current["text"] += f"\nReference screenshot:\n{urljoin(base_url, src)}\n"

        elif tag.name == "video":
            src = tag.get("src")
            if src:
                current["text"] += f"\nReference video:\n{urljoin(base_url, src)}\n"

        else:
            text = fix_encoding(tag.get_text(" ", strip=True))
            if text:
                current["text"] += text + "\n"

    if current["text"].strip():
        current["text"] = normalize_text(current["text"])
        sections.append(current)

    return {"title": title, "sections": sections}


# ══════════════════════════════════════════════════════════════
#  STEP 4 — RAG CHUNKING
# ══════════════════════════════════════════════════════════════

def make_chunk_id(stem: str, url: str, idx: int, heading: str) -> str:
    path_slug = re.sub(r'[^a-zA-Z0-9]', '_', urlparse(url).path.strip("/")) or "root"
    head_slug = re.sub(r'[^a-zA-Z0-9]', '_', heading)[:40]
    return f"{stem}__{path_slug}__{idx}__{head_slug}"


def make_doc_id(url: str) -> str:
    path = urlparse(url).path.strip("/")
    return path or "root"


def content_hash(url: str, heading: str, text: str) -> str:
    return hashlib.md5(f"{url}|{heading}|{text[:120]}".encode()).hexdigest()


def token_estimate(text: str) -> int:
    return max(1, len(text) // 4)


def is_noise(text: str) -> bool:
    s = text.strip()
    if len(s) < 30:
        return True
    lines = [l.strip() for l in s.splitlines() if l.strip()]
    if lines and all(l.startswith("http") for l in lines):
        return True
    return False


def pages_to_chunks(pages: list[dict], stem: str) -> list[dict]:
    chunks: list[dict] = []
    seen_hashes: set[str] = set()

    for page in pages:
        url    = page.get("url", "")
        title  = page.get("title", "")
        doc_id = make_doc_id(url)

        for idx, section in enumerate(page.get("sections", [])):
            heading  = (section.get("heading") or "Content").strip()
            raw_text = section.get("text", "")
            text     = raw_text.strip()

            if is_noise(text):
                continue

            # Full embedding text: title + heading + body
            embed_text = f"{title}\n{heading}\n\n{text}"
            h = content_hash(url, heading, text)

            if h in seen_hashes:
                continue
            seen_hashes.add(h)

            chunks.append({
                "chunk_id":  make_chunk_id(stem, url, idx, heading),
                "doc_id":    doc_id,
                "url":       url,
                "title":     title,
                "heading":   heading,
                "text":      embed_text,
                "char_count": len(embed_text),
                "token_est": token_estimate(embed_text),
            })

    return chunks


# ══════════════════════════════════════════════════════════════
#  MAIN PIPELINE
# ══════════════════════════════════════════════════════════════

def run(raw_url: str, delay: float = 1.0, limit: int = 0, save: bool = True) -> dict:
    timestamp = datetime.now(timezone.utc).isoformat()
    errors: list[str] = []

    # ── Sanitize ──────────────────────────────────────────────
    try:
        base = sanitize_url(raw_url)
    except ValueError as e:
        return _fail(raw_url, None, str(e), timestamp, save)

    stem = hostname_stem(base)
    _banner(f"Target: {base}")

    # ── Sitemap ───────────────────────────────────────────────
    _step(1, 4, "Discovering sitemap")
    sitemap_url, page_urls = get_sitemap_urls(base, errors)

    if not sitemap_url:
        _err("No sitemap found.")
        return _fail(raw_url, base, "Sitemap not Found", timestamp, save, stem, errors)

    total_discovered = len(page_urls)
    print(f"     ✓  {sitemap_url}")
    print(f"     ✓  {total_discovered} URLs discovered")

    if limit:
        page_urls = page_urls[:limit]
        print(f"     ⚡  Limit applied → scraping first {limit}")

    # ── Scrape ────────────────────────────────────────────────
    _step(2, 4, f"Scraping {len(page_urls)} pages")
    pages:  list[dict] = []
    failed: list[str]  = []

    for idx, url in enumerate(page_urls, 1):
        label = f"  [{idx:4d}/{len(page_urls)}]  {url}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
            content = extract_page(r.text, url)
            pages.append({"url": url, "title": content["title"], "sections": content["sections"]})
            print(f"{label}  ✓  ({len(content['sections'])} sections)")
        except Exception as e:
            print(f"{label}  ✗  {e}")
            failed.append(url)
            errors.append(f"Scrape failed {url}: {e}")

        if delay > 0:
            time.sleep(delay)

    # ── RAG Chunking ──────────────────────────────────────────
    _step(3, 4, "Building RAG chunks")
    chunks = pages_to_chunks(pages, stem)
    print(f"     ✓  {len(chunks)} chunks created from {len(pages)} pages")

    # ── Save ──────────────────────────────────────────────────
    _step(4, 4, "Saving output")

    result = {
        "meta": {
            "task":             "RAG Pipeline",
            "status":           "success",
            "input_url":        raw_url,
            "base_url":         base,
            "sitemap_url":      sitemap_url,
            "total_discovered": total_discovered,
            "scraped":          len(pages),
            "failed":           len(failed),
            "failed_urls":      failed,
            "total_chunks":     len(chunks),
            "errors":           errors,
            "generated_at":     timestamp,
        },
        "chunks": chunks,
    }

    filename = f"{stem}_rag_data.json"
    if save:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

    _banner(
        f"Status   : SUCCESS\n"
        f"  Scraped  : {len(pages)} / {len(page_urls)}\n"
        f"  Failed   : {len(failed)}\n"
        f"  Chunks   : {len(chunks)}\n"
        f"  Output   : {filename if save else '(not saved)'}"
    )

    # Print one sample chunk
    if chunks:
        print("\n  Sample chunk:\n")
        print(json.dumps(chunks[0], indent=4, ensure_ascii=False))

    return result


# ── Helpers ───────────────────────────────────────────────────

def _fail(raw, base, reason, ts, save, stem="failed", errors=None):
    result = {
        "meta": {
            "task":         "RAG Pipeline",
            "status":       "failed",
            "input_url":    raw,
            "base_url":     base,
            "result":       reason,
            "errors":       errors or [reason],
            "generated_at": ts,
        },
        "chunks": [],
    }
    if save:
        fname = f"{stem}_rag.json"
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n  💾 Saved → {fname}")
    else:
        print(json.dumps(result, indent=2))
    return result


def _banner(msg: str):
    print(f"\n{'═'*55}")
    print(f"  {msg}")
    print(f"{'═'*55}")


def _step(n: int, total: int, msg: str):
    print(f"\n[{n}/{total}] {msg} …")


def _err(msg: str):
    print(f"     ✗  {msg}")


# ══════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(
        description="Scrape any website and export RAG-ready chunks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python data_fetcher.py oppiwallet.com
  python data_fetcher.py www.example.com --delay 2
  python data_fetcher.py https://example.com --limit 100
  python data_fetcher.py example.com --no-save
        """
    )
    ap.add_argument("url",
                    help="Website URL — any format: oppiwallet.com / www.x.com / https://x.com")
    ap.add_argument("--delay",   type=float, default=1.0,
                    help="Seconds between requests (default: 1.0)")
    ap.add_argument("--limit",   type=int,   default=0,
                    help="Max pages to scrape; 0 = all (default: 0)")
    ap.add_argument("--no-save", action="store_true",
                    help="Print summary only, do not write file")
    args = ap.parse_args()

    run(
        raw_url = args.url,
        delay   = args.delay,
        limit   = args.limit,
        save    = not args.no_save,
    )


if __name__ == "__main__":
    main()



'''
 python url_to_data.py oppiwallet.com
'''