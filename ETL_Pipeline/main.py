"""
ETL Pipeline — Playage User Guide Crawler
==========================================
Admin-only FastAPI service. Triggered on-demand via POST /trigger.
Crawls 4 Playage userguide sections, detects changes, saves versioned JSON.

Auth : Bearer tmkoc_23prteam_bas_crm_cms_bo_final_version_1.0_7542321
Start : uvicorn main:app --host 0.0.0.0 --port 8010 --reload
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time
import uuid
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from readability import Document
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from urllib.parse import urljoin, urlparse, urlunparse

try:
    import ftfy
    HAS_FTFY = True
except ImportError:
    HAS_FTFY = False


# ══════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════

API_ACCESS_KEY = "tmkoc_23prteam_bas_crm_cms_bo_final_version_1.0_7542321"

SOURCES = [
    "https://userguide.playagegaming.tech/en/bo/",
    "https://userguide.playagegaming.tech/en/cms/",
    "https://userguide.playagegaming.tech/en/crm/",
    "https://userguide.playagegaming.tech/en/bas/",
]

SITEMAP_BASE = "https://userguide.playagegaming.tech"
OUTPUT_DIR   = Path(__file__).parent          # ETL_Pipeline/
LOG_FILE     = OUTPUT_DIR / "etl_pipeline.log"

MAX_VERSIONS_TO_KEEP = 2    # keep 2 previous JSON files as backup
REQUEST_DELAY        = 1.0  # seconds between page scrapes
REQUEST_TIMEOUT      = 20   # seconds per HTTP request
MAX_TRIGGER_RPS      = "2/minute"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

BLACKLIST_PHRASES = [
    "Confidential Document",
    "Enterprise Management System",
    "For Authorized Personnel Only",
]

SITEMAP_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap/sitemap.xml",
]


# ══════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("etl_pipeline")


# ══════════════════════════════════════════════════════════════
#  GLOBAL RUN STATE
# ══════════════════════════════════════════════════════════════

run_state: dict[str, Any] = {
    "status":          "idle",            # idle | running | completed | no_changes | error
    "run_id":          None,
    "started_at":      None,
    "finished_at":     None,
    "duration_seconds": None,
    "pages_scraped":   None,
    "changes_detected": None,
    "output_file":     None,
    "source_breakdown": {},              # per-source page counts  {"BO": 42, "CMS": 30, ...}
    "message":         "No runs yet.",
    "errors":          [],
}

_run_lock = asyncio.Lock()   # prevents concurrent triggers


# ══════════════════════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════════════════════

security = HTTPBearer()


def verify_bearer(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency: validate Bearer token for admin endpoints."""
    if credentials.credentials != API_ACCESS_KEY:
        log.warning("Unauthorized access attempt — wrong Bearer token.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API access key.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


# ══════════════════════════════════════════════════════════════
#  FASTAPI APP + RATE LIMITER
# ══════════════════════════════════════════════════════════════

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    title="Playage ETL Pipeline",
    description="Admin-only service: crawl Playage userguide → versioned JSON",
    version="1.0.0",
    # docs_url=None,       # hide Swagger from public
    # redoc_url=None,
    # openapi_url=None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ══════════════════════════════════════════════════════════════
#  TEXT UTILITIES  (ported from url_to_data.py / crawl_pages.py)
# ══════════════════════════════════════════════════════════════

def fix_encoding(text: str) -> str:
    return ftfy.fix_text(text) if HAS_FTFY else text


def normalize_text(text: str) -> str:
    text = fix_encoding(text)
    seen: set[str] = set()
    lines: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if s and s not in seen:
            seen.add(s)
            lines.append(s)
    text = "\n".join(lines)
    for phrase in BLACKLIST_PHRASES:
        text = text.replace(phrase, "")
    cleaned: list[str] = []
    for line in text.splitlines():
        low = line.lower()
        if not ("professional documentation" in low and "version" in low):
            cleaned.append(line)
    return "\n".join(cleaned).strip()


# ══════════════════════════════════════════════════════════════
#  STEP 1 — URL DISCOVERY  (BFS link crawler)
#
#  GitBook sites do not expose sitemap.xml.
#  We BFS-crawl from each of the 4 known section root URLs,
#  following only internal links that stay within the same
#  /en/<section>/ prefix — exactly how the existing data was built.
# ══════════════════════════════════════════════════════════════

def _http_get(url: str, timeout: int = REQUEST_TIMEOUT) -> Optional[requests.Response]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            return r
    except Exception as exc:
        log.debug("GET %s → %s", url, exc)
    return None


def _extract_internal_links(html: str, base_url: str, prefix: str) -> list[str]:
    """
    Parse <a href> links, resolve to absolute URLs, keep only those
    inside `prefix` (e.g. https://.../en/bo/).
    """
    soup = BeautifulSoup(html, "html.parser")
    found: list[str] = []
    seen_paths: set[str] = set()
    for tag in soup.find_all("a", href=True):
        raw = tag["href"].strip()
        if not raw or raw.startswith("#") or raw.startswith("mailto:"):
            continue
        resolved = urljoin(base_url, raw)
        p = urlparse(resolved)
        # Normalise: always trailing slash, no query/fragment
        clean = urlunparse((p.scheme, p.netloc, p.path.rstrip("/") + "/", "", "", ""))
        if clean.startswith(prefix) and clean != prefix and p.path not in seen_paths:
            seen_paths.add(p.path)
            found.append(clean)
    return found


def _crawl_section(root_url: str, errors: list[str]) -> list[str]:
    """BFS from root_url, collecting all reachable pages within the same section."""
    visited:   set[str]  = set()
    queue:     list[str] = [root_url]
    collected: list[str] = []

    while queue:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        r = _http_get(url)
        if not r:
            errors.append(f"BFS: cannot fetch {url}")
            continue

        if url != root_url:      # root is index/nav page, skip as a doc
            collected.append(url)

        for link in _extract_internal_links(r.text, url, root_url):
            if link not in visited:
                queue.append(link)

        time.sleep(0.3)          # polite BFS delay

    return collected


def _try_sitemap_xml(errors: list[str]) -> list[str]:
    """Try robots.txt + common paths for a sitemap XML. Returns URLs or []."""
    sitemap_url: Optional[str] = None
    r = _http_get(f"{SITEMAP_BASE}/robots.txt")
    if r:
        for line in r.text.splitlines():
            if line.lower().startswith("sitemap:"):
                sitemap_url = line.split(":", 1)[1].strip()
                break
    if not sitemap_url:
        for path in SITEMAP_PATHS:
            candidate = SITEMAP_BASE.rstrip("/") + path
            r = _http_get(candidate)
            if r and ("<urlset" in r.text or "<sitemapindex" in r.text):
                sitemap_url = candidate
                break
    if not sitemap_url:
        return []

    log.info("Sitemap XML found: %s", sitemap_url)
    raw: list[str] = []
    visited_s: set[str] = set()

    def _parse(url: str):
        if url in visited_s:
            return
        visited_s.add(url)
        resp = _http_get(url)
        if not resp:
            return
        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError:
            return
        ns  = "{http://www.sitemaps.org/schemas/sitemap/0.9}loc"
        tag = root.tag.lower()
        if "sitemapindex" in tag:
            for child in [loc.text.strip() for loc in root.iter(ns) if loc.text]:
                _parse(child)
        elif "urlset" in tag:
            raw.extend([loc.text.strip() for loc in root.iter(ns) if loc.text])

    _parse(sitemap_url)
    allowed = tuple(SOURCES)
    return list(dict.fromkeys(u for u in raw if u.startswith(allowed)))


def discover_sitemap_urls(errors: list[str]) -> list[str]:
    """
    Discover page URLs from the 4 monitored sections.
    Strategy A: sitemap XML (future-proof if the site adds one).
    Strategy B: BFS link crawl from each section root (works for GitBook).
    """
    # A. Sitemap XML
    xml_urls = _try_sitemap_xml(errors)
    if xml_urls:
        log.info("Sitemap XML: %d target URLs discovered", len(xml_urls))
        return xml_urls

    # B. BFS crawl
    log.info("No sitemap.xml found — BFS crawling %d section roots…", len(SOURCES))
    all_urls: list[str] = []
    for src in SOURCES:
        label = src.rstrip("/").split("/")[-1].upper()
        log.info("  BFS → %s  (%s)", label, src)
        section_urls = _crawl_section(src, errors)
        log.info("  %s: %d pages found", label, len(section_urls))
        all_urls.extend(section_urls)

    unique = list(dict.fromkeys(all_urls))
    log.info("BFS total discovered: %d pages", len(unique))

    if not unique:
        errors.append("BFS crawler found no pages — check source URLs and network access.")
    return unique


# ══════════════════════════════════════════════════════════════
#  STEP 2 — PAGE SCRAPING
# ══════════════════════════════════════════════════════════════

def _extract_page_content(html: str, base_url: str) -> dict:
    """Extract title + structured sections from raw HTML."""
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
                current["text"] += (
                    "\nReference screenshot for documentation purposes:\n"
                    f"{urljoin(base_url, src)}\n"
                )

        elif tag.name == "video":
            src = tag.get("src")
            if src:
                current["text"] += (
                    "\nReference video for documentation purposes:\n"
                    f"{urljoin(base_url, src)}\n"
                )

        else:
            text = fix_encoding(tag.get_text(" ", strip=True))
            if text:
                current["text"] += text + "\n"

    if current["text"].strip():
        current["text"] = normalize_text(current["text"])
        sections.append(current)

    return {"title": title, "sections": sections}


def _build_doc_id(url: str) -> str:
    """
    Converts URL path to doc_id matching the existing JSON schema.
    e.g. /en/bo/player-management/3-1-1/ → player-management/3-1-1
    """
    path_parts = urlparse(url).path.strip("/").split("/")
    # path_parts = ['en', 'bo', 'player-management', '3-1-1']
    # Skip 'en' and module ('bo'/'cms'/'crm'/'bas')
    relevant = path_parts[2:]  # ['player-management', '3-1-1'] or ['payments']
    if not relevant or relevant == ['']:
        return "root"
    return "/".join(relevant)


def _page_to_document(url: str, page_content: dict) -> dict:
    """Convert scraped page data to the target JSON document format."""
    title    = page_content["title"]
    sections = page_content["sections"]
    doc_id   = _build_doc_id(url)

    # Flatten all sections into single 'section' string (matches refined_all schema)
    section_parts: list[str] = []
    for sec in sections:
        heading = sec.get("heading", "").strip()
        text    = sec.get("text", "").strip()
        if heading and text:
            section_parts.append(f"{heading}\n{text}")
        elif text:
            section_parts.append(text)
        elif heading:
            section_parts.append(heading)

    section_str = "\n\n".join(section_parts)

    return {
        "doc_id":  doc_id,
        "url":     url,
        "title":   title,
        "section": section_str,
    }


def scrape_all_pages(urls: list[str]) -> tuple[list[dict], list[str]]:
    """Scrape all URLs, return (documents, failed_urls)."""
    documents: list[dict] = []
    failed:    list[str]  = []
    total = len(urls)

    for idx, url in enumerate(urls, 1):
        log.info("[%d/%d] Scraping %s", idx, total, url)
        try:
            r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            page_content = _extract_page_content(r.text, url)
            doc = _page_to_document(url, page_content)
            # Skip docs with no meaningful content
            if doc["section"].strip():
                documents.append(doc)
        except Exception as exc:
            log.warning("  ✗ Failed: %s → %s", url, exc)
            failed.append(url)

        if idx < total:
            time.sleep(REQUEST_DELAY)

    return documents, failed


# ══════════════════════════════════════════════════════════════
#  STEP 3 — CHANGE DETECTION
# ══════════════════════════════════════════════════════════════

def _doc_hash(doc: dict) -> str:
    key = f"{doc['url']}|{doc.get('section', '')[:500]}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def detect_changes(new_docs: list[dict], existing_file: Optional[Path]) -> int:
    """
    Returns number of changed/added documents compared to existing JSON.
    If no existing file, all docs are considered 'new'.
    """
    if existing_file is None or not existing_file.exists():
        return len(new_docs)

    try:
        with open(existing_file, "r", encoding="utf-8") as f:
            existing_docs: list[dict] = json.load(f)
    except Exception:
        return len(new_docs)

    existing_hashes = {_doc_hash(d) for d in existing_docs}
    changed = sum(1 for d in new_docs if _doc_hash(d) not in existing_hashes)
    return changed


# ══════════════════════════════════════════════════════════════
#  STEP 4 — VERSION CONTROL
# ══════════════════════════════════════════════════════════════

_JSON_PATTERN = re.compile(r"^refined_all_\d{8}\.json$")


def _list_versioned_files() -> list[Path]:
    """Return existing versioned JSON files sorted oldest-first."""
    files = sorted(
        [p for p in OUTPUT_DIR.glob("refined_all_*.json") if _JSON_PATTERN.match(p.name)]
    )
    return files


def rotate_versions():
    """
    Keep only MAX_VERSIONS_TO_KEEP (2) previous JSON files.
    Deletes the oldest ones first.
    """
    existing = _list_versioned_files()
    # We are about to add one more, so we need to drop any excess
    while len(existing) > MAX_VERSIONS_TO_KEEP:
        oldest = existing.pop(0)
        try:
            oldest.unlink()
            log.info("Version control: deleted old backup → %s", oldest.name)
        except Exception as exc:
            log.warning("Could not delete %s: %s", oldest.name, exc)


def output_filename() -> Path:
    """Generate today's output filename: refined_all_DDMMYYYY.json"""
    today = datetime.now().strftime("%d%m%Y")
    return OUTPUT_DIR / f"refined_all_{today}.json"


def save_output(documents: list[dict]) -> Path:
    """Rotate old versions, write new JSON file, return path."""
    rotate_versions()
    out_path = output_filename()
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(documents, f, indent=2, ensure_ascii=False)
    log.info("Output saved → %s  (%d documents)", out_path.name, len(documents))
    return out_path


# ══════════════════════════════════════════════════════════════
#  FULL PIPELINE RUNNER
# ══════════════════════════════════════════════════════════════

def _get_latest_json() -> Optional[Path]:
    existing = _list_versioned_files()
    return existing[-1] if existing else None


def run_etl_pipeline(run_id: str):
    """Blocking pipeline function — run in thread executor."""
    global run_state

    t_start = time.monotonic()
    run_state.update({
        "status":          "running",
        "run_id":          run_id,
        "started_at":      datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat(),
        "finished_at":     None,
        "duration_seconds": None,
        "pages_scraped":   None,
        "changes_detected": None,
        "output_file":     None,
        "source_breakdown": {},
        "message":         "Pipeline running…",
        "errors":          [],
    })

    errors: list[str] = []

    try:
        # ── 1. Discover URLs ──────────────────────────────────
        log.info("=== ETL Pipeline Run %s ===", run_id)
        log.info("Step 1/4: Discovering sitemap URLs…")
        urls = discover_sitemap_urls(errors)

        if not urls:
            _finish_state("error", run_id, t_start, 0, 0, None, "No URLs discovered from sitemap.", errors)
            return

        # ── 2. Scrape pages ───────────────────────────────────
        log.info("Step 2/4: Scraping %d pages…", len(urls))
        documents, failed = scrape_all_pages(urls)
        errors.extend([f"Scrape failed: {u}" for u in failed])

        # Per-source breakdown
        breakdown: dict[str, int] = {}
        for src in SOURCES:
            label = src.rstrip("/").split("/")[-1].upper()   # bo→BO, cms→CMS …
            breakdown[label] = sum(1 for d in documents if d["url"].startswith(src))
        run_state["source_breakdown"] = breakdown

        log.info(
            "Pages per source  │  %s  │  Total: %d",
            "  ".join(f"{k}: {v}" for k, v in breakdown.items()),
            len(documents),
        )

        if not documents:
            _finish_state("error", run_id, t_start, 0, 0, None, "No documents scraped.", errors)
            return

        # ── 3. Change detection ───────────────────────────────
        log.info("Step 3/4: Detecting changes…")
        latest_file  = _get_latest_json()
        changes      = detect_changes(documents, latest_file)

        if changes == 0:
            log.info("No changes detected. Skipping save.")
            _finish_state(
                "no_changes", run_id, t_start,
                len(documents), 0, None,
                "No changes detected in source data. Existing JSON is current.",
                errors,
            )
            return

        log.info("%d change(s) detected.", changes)

        # ── 4. Save versioned JSON ────────────────────────────
        log.info("Step 4/4: Saving versioned output…")
        out_path = save_output(documents)

        _finish_state(
            "completed", run_id, t_start,
            len(documents), changes, out_path.name,
            f"Pipeline completed. {changes} change(s) detected. Output: {out_path.name}",
            errors,
        )

    except Exception as exc:
        log.exception("Unhandled pipeline error: %s", exc)
        _finish_state("error", run_id, t_start, 0, 0, None, str(exc), errors + [str(exc)])


def _finish_state(
    pipeline_status: str,
    run_id: str,
    t_start: float,
    pages: int,
    changes: int,
    outfile: Optional[str],
    message: str,
    errors: list[str],
):
    global run_state
    duration = round(time.monotonic() - t_start, 2)
    finished = datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat()
    run_state.update({
        "status":          pipeline_status,
        "run_id":          run_id,
        "finished_at":     finished,
        "duration_seconds": duration,
        "pages_scraped":   pages,
        "changes_detected": changes,
        "output_file":     outfile,
        "message":         message,
        "errors":          errors,
    })
    _STATUS_ICON = {
        "completed":  "✅",
        "no_changes": "ℹ️ ",
        "error":      "❌",
    }
    icon = _STATUS_ICON.get(pipeline_status, "🔄")
    breakdown = run_state.get("source_breakdown", {})
    source_str = "  ".join(f"{k}:{v}" for k, v in breakdown.items()) if breakdown else "—"
    log.info(
        "%s  Run %-8s  │  status=%-12s  │  total=%d  │  [%s]  │  changes=%d  │  %.2fs",
        icon, run_id, pipeline_status.upper(), pages, source_str, changes, duration,
    )


# ══════════════════════════════════════════════════════════════
#  THREAD EXECUTOR  (keeps FastAPI event loop unblocked)
# ══════════════════════════════════════════════════════════════

_executor = ThreadPoolExecutor(max_workers=1)


async def _run_pipeline_async(run_id: str):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(_executor, run_etl_pipeline, run_id)


# ══════════════════════════════════════════════════════════════
#  ENDPOINTS
# ══════════════════════════════════════════════════════════════

@app.get(
    "/system-health-area",
    summary="ETL Pipeline Health Check",
    tags=["System"],
)
def system_health():
    """
    Public liveness check.
    Returns pipeline status, current timestamp (IST), and the 4 monitored source URLs.
    No auth required — this endpoint confirms the service is running.
    """
    now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat()
    return JSONResponse(
        status_code=200,
        content={
            "service":   "Playage ETL Pipeline",
            "health":    "ETL pipeline working smoothly",
            "timestamp": now_ist,
            "sources":   SOURCES,
        },
    )


@app.post(
    "/trigger",
    summary="Trigger ETL Pipeline",
    tags=["Admin"],
    status_code=202,
)
@limiter.limit(MAX_TRIGGER_RPS)
async def trigger_pipeline(
    request: Request,
    _key: str = Depends(verify_bearer),
):
    """
    **Admin only** — triggers a full crawl & extract pipeline run.

    - Returns `202 Accepted` immediately with a `run_id`.
    - The pipeline runs in the background.
    - Poll `GET /status` to check progress.
    - Rate-limited: max 2 requests/minute per IP.
    """
    async with _run_lock:
        if run_state["status"] == "running":
            raise HTTPException(
                status_code=409,
                detail="A pipeline run is already in progress. Check /status for updates.",
            )
        run_id = str(uuid.uuid4())[:8]
        run_state["status"]   = "running"
        run_state["run_id"]   = run_id
        run_state["message"]  = "Queued…"

    asyncio.create_task(_run_pipeline_async(run_id))

    now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat()
    return {
        "accepted":    True,
        "run_id":      run_id,
        "message":     "Pipeline triggered. Check /status for progress.",
        "timestamp":   now_ist,
        "poll_url":    "/status",
    }


@app.get(
    "/status",
    summary="Pipeline Status",
    tags=["Admin"],
)
def get_status(_key: str = Depends(verify_bearer)):
    """
    **Admin only** — returns current or last pipeline run state.

    Possible `status` values:
    - `idle`        — never triggered
    - `running`     — currently crawling
    - `completed`   — finished with changes saved
    - `no_changes`  — finished, source data unchanged
    - `error`       — pipeline encountered a fatal error
    """
    versioned_files = [p.name for p in _list_versioned_files()]
    return {
        **run_state,
        "versioned_files": versioned_files,
    }


@app.get(
    "/data",
    summary="Get Latest Extracted JSON Data",
    tags=["Admin"],
)
def get_data(_key: str = Depends(verify_bearer)):
    """
    **Admin only** — returns the full document array from the latest saved JSON file.

    Response includes:
    - `data_status`: human-readable label (e.g. "New data available", "No new data found")
    - `source_file`: which file was read
    - `total_documents`: count of docs in the file
    - `generated_at`: timestamp of the file (from the last pipeline run)
    - `documents`: the full extracted JSON array
    """
    latest_file = _get_latest_json()
    now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat()

    if latest_file is None or not latest_file.exists():
        return JSONResponse(
            status_code=200,
            content={
                "data_status":      "No data found — pipeline has not run yet",
                "source_file":      None,
                "total_documents":  0,
                "generated_at":     now_ist,
                "documents":        [],
            },
        )

    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            documents: list[dict] = json.load(f)
    except Exception as exc:
        log.error("Failed to read latest JSON: %s", exc)
        raise HTTPException(status_code=500, detail=f"Could not read data file: {exc}")

    # Determine data-freshness label based on last run state
    last_state  = run_state.get("status", "idle")
    last_output = run_state.get("output_file")

    if last_state == "no_changes":
        data_status = "No new data found — source content is unchanged since last run"
    elif last_state == "completed" and last_output == latest_file.name:
        data_status = "New data available — updated from latest pipeline run"
    elif last_state == "running":
        data_status = "Pipeline currently running — showing previous data"
    elif last_state == "idle":
        data_status = "Showing existing data — pipeline not yet triggered in this session"
    else:
        data_status = "Data available"

    return JSONResponse(
        status_code=200,
        content={
            "data_status":      data_status,
            "source_file":      latest_file.name,
            "total_documents":  len(documents),
            "generated_at":     now_ist,
            "documents":        documents,
        },
    )


# ══════════════════════════════════════════════════════════════
#  APP STARTUP LOG
# ══════════════════════════════════════════════════════════════

def _print_startup_banner():
    """Print a professional startup banner to the console."""
    now_ist    = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d %H:%M:%S IST")
    files      = [p.name for p in _list_versioned_files()]
    file_label = files[-1] if files else "none"
    w = 62  # box width

    lines = [
        "",
        "╔" + "═" * w + "╗",
        "║" + "  🚀  PLAYAGE ETL PIPELINE  v1.0.0".center(w) + "║",
        "║" + "  Admin-only Crawl & Extract Service".center(w) + "║",
        "╠" + "═" * w + "╣",
        f"║  {'Status':<18}  ETL pipeline working smoothly" .ljust(w) + " ║",
        f"║  {'Started at':<18}  {now_ist}".ljust(w) + " ║",
        f"║  {'Port':<18}  8010".ljust(w) + " ║",
        f"║  {'Latest data file':<18}  {file_label}".ljust(w) + " ║",
        f"║  {'Versioned backups':<18}  {len(files)}".ljust(w) + " ║",
        "╠" + "═" * w + "╣",
        "║" + "  Monitored Sources:".ljust(w) + "║",
    ]
    for src in SOURCES:
        lines.append(f"║    • {src}".ljust(w + 1) + "║")
    lines += [
        "╠" + "═" * w + "╣",
        "║" + "  Endpoints:".ljust(w) + "║",
        "║    GET  /system-health-area   (public)".ljust(w + 1) + "║",
        "║    POST /trigger              (Bearer auth)".ljust(w + 1) + "║",
        "║    GET  /status               (Bearer auth)".ljust(w + 1) + "║",
        "║    GET  /data                 (Bearer auth)".ljust(w + 1) + "║",
        "╚" + "═" * w + "╝",
        "",
    ]
    for line in lines:
        print(line)


@app.on_event("startup")
async def _startup():
    _print_startup_banner()
    log.info("Playage ETL Pipeline started.")
    log.info("Output directory    : %s", OUTPUT_DIR)
    log.info("Monitored sources   : %s", SOURCES)
    log.info("Existing JSON files : %s", [p.name for p in _list_versioned_files()])


# ══════════════════════════════════════════════════════════════
#  TREE BUILDER
# ══════════════════════════════════════════════════════════════

MODULE_META = {
    "bo":  {"label": "Back Office",                      "color": "#3b82f6"},
    "cms": {"label": "Content Management System",        "color": "#a855f7"},
    "crm": {"label": "Customer Relationship Management", "color": "#22c55e"},
    "bas": {"label": "Business Analytics System",        "color": "#f59e0b"},
}


def _build_tree(documents: list[dict]) -> dict:
    """
    Build a hierarchical tree from the flat documents list.
    Structure: root → module (BO/CMS/CRM/BAS) → category → pages
    """
    now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat()
    modules: dict = {}

    for doc in documents:
        url    = doc.get("url", "")
        doc_id = doc.get("doc_id", "root")
        title  = doc.get("title", "")

        # Identify module from URL
        mod_key = "unknown"
        for src in SOURCES:
            if url.startswith(src):
                mod_key = src.rstrip("/").split("/")[-1]   # bo | cms | crm | bas
                break

        mod_upper = mod_key.upper()
        if mod_upper not in modules:
            meta = MODULE_META.get(mod_key, {"label": mod_upper, "color": "#6b7280"})
            modules[mod_upper] = {
                "key":        mod_upper,
                "label":      meta["label"],
                "color":      meta["color"],
                "total":      0,
                "categories": {},
            }

        modules[mod_upper]["total"] += 1

        # Split doc_id into category / page_id
        parts    = [p for p in doc_id.strip("/").split("/") if p]
        category = parts[0] if parts else "overview"
        page_id  = "/".join(parts[1:]) if len(parts) > 1 else ""

        cats = modules[mod_upper]["categories"]
        if category not in cats:
            cats[category] = {
                "name":  category.replace("-", " ").title(),
                "slug":  category,
                "total": 0,
                "pages": [],
            }
        cats[category]["total"] += 1
        cats[category]["pages"].append({
            "doc_id":  doc_id,
            "page_id": page_id or category,
            "title":   title,
            "url":     url,
        })

    # Sort pages within each category by page_id (numeric-aware)
    def _page_sort_key(p: dict) -> list:
        return [int(x) if x.isdigit() else x
                for x in p["page_id"].replace("-", ".").split(".")]

    for mod in modules.values():
        for cat in mod["categories"].values():
            try:
                cat["pages"].sort(key=_page_sort_key)
            except Exception:
                pass
        mod["categories"] = dict(sorted(mod["categories"].items()))

    return {
        "generated_at":    now_ist,
        "total_documents": len(documents),
        "total_modules":   len(modules),
        "source_file":     (_get_latest_json() or Path("none")).name,
        "modules":         modules,
    }


# ══════════════════════════════════════════════════════════════
#  ENDPOINTS — TREE & EXPLORER
# ══════════════════════════════════════════════════════════════

@app.get(
    "/tree",
    summary="Backoffice Tree Structure",
    tags=["Admin"],
)
def get_tree(_key: str = Depends(verify_bearer)):
    """
    **Admin only** — returns a hierarchical JSON tree of the entire
    Playage Backoffice documentation.
    Structure: `modules → categories → pages`
    """
    from fastapi.responses import JSONResponse as _JSONResponse
    latest_file = _get_latest_json()
    if latest_file is None or not latest_file.exists():
        return _JSONResponse(status_code=200, content={
            "message": "No data yet — trigger the pipeline first.",
            "modules": {}, "total_documents": 0,
        })
    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            documents: list[dict] = json.load(f)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not read data file: {exc}")

    return JSONResponse(status_code=200, content=_build_tree(documents))


@app.get("/explorer", include_in_schema=False)
def explorer():
    """Public — serves the interactive tree explorer HTML page."""
    from fastapi.responses import HTMLResponse as _HTMLResponse
    html_path = OUTPUT_DIR / "index.html"
    if not html_path.exists():
        return _HTMLResponse(
            content="<h2 style='font-family:sans-serif;padding:40px'>index.html not found. "
                    "Make sure index.html is in the ETL_Pipeline directory.</h2>",
            status_code=404,
        )
    return _HTMLResponse(content=html_path.read_text(encoding="utf-8"))
