"""
Sitemap URL Extractor → JSON
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fetches all URLs from a website's sitemap.xml and saves as JSON.

Usage:
    python sitemap.py https://example.com
    python sitemap.py example.com
    python sitemap.py www.example.com
"""

import xml.etree.ElementTree as ET
import argparse
import json
import re
import requests
from datetime import datetime, timezone
from urllib.parse import urlparse

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


# ─── URL Sanitizer ────────────────────────────────────────────────────────────

def sanitize_url(raw: str) -> str:
    """
    Normalize any user-provided URL to a clean base URL.
    Handles missing scheme, www variants, trailing slashes, paths, etc.

    Examples:
        example.com          → https://example.com
        www.example.com      → https://www.example.com
        http://example.com/  → https://example.com
        HTTPS://Example.COM  → https://example.com
        example.com/some/page→ https://example.com
    """
    raw = raw.strip()

    # Remove any leading/trailing quotes
    raw = raw.strip("'\"")

    # If no scheme, prepend https://
    if not re.match(r'^https?://', raw, re.IGNORECASE):
        raw = "https://" + raw

    parsed = urlparse(raw)

    scheme   = "https"                        # always upgrade to https
    hostname = (parsed.hostname or "").lower().rstrip(".")
    port     = parsed.port

    if not hostname:
        raise ValueError(f"Could not parse a valid hostname from: {raw!r}")

    base = f"{scheme}://{hostname}"
    if port and port not in (80, 443):
        base += f":{port}"

    return base


def hostname_to_filename(base: str) -> str:
    """Turn https://sub.example.com → sub_example_com (safe filename stem)."""
    hostname = urlparse(base).hostname or "site"
    return re.sub(r'[^a-zA-Z0-9]', '_', hostname)


# ─── HTTP helper ──────────────────────────────────────────────────────────────

def get(url: str) -> "requests.Response | None":
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r
    except Exception:
        pass
    return None


# ─── Sitemap discovery ────────────────────────────────────────────────────────

def find_sitemap_url(base: str) -> "str | None":
    """Check robots.txt first, then try common paths."""
    r = get(f"{base}/robots.txt")
    if r:
        for line in r.text.splitlines():
            if line.lower().startswith("sitemap:"):
                url = line.split(":", 1)[1].strip()
                return url

    for path in SITEMAP_PATHS:
        url = base.rstrip("/") + path
        r = get(url)
        if r and ("<urlset" in r.text or "<sitemapindex" in r.text):
            return url

    return None


# ─── Sitemap parser ───────────────────────────────────────────────────────────

def parse_sitemap(url: str, collected: list, visited: set, errors: list):
    """Recursively parse sitemap or sitemap index."""
    if url in visited:
        return
    visited.add(url)

    r = get(url)
    if not r:
        errors.append(f"Could not fetch: {url}")
        return

    try:
        root = ET.fromstring(r.content)
    except ET.ParseError as e:
        errors.append(f"XML parse error at {url}: {e}")
        return

    tag = root.tag.lower()

    if "sitemapindex" in tag:
        child_urls = [
            loc.text.strip()
            for loc in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
            if loc.text
        ]
        for child_url in child_urls:
            parse_sitemap(child_url, collected, visited, errors)

    elif "urlset" in tag:
        locs = [
            loc.text.strip()
            for loc in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
            if loc.text
        ]
        collected.extend(locs)


# ─── Core module function ─────────────────────────────────────────────────────

def extract_sitemap(raw_url: str, save: bool = True) -> dict:
    """
    Main entry point. Accepts any URL string, returns a result dict,
    and optionally saves <sitename>_sitemap.json.

    Return schema
    ─────────────
    Success:
    {
      "task":        "Sitemap Extraction",
      "status":      "success",
      "input_url":   "<original input>",
      "base_url":    "<sanitized base>",
      "sitemap_url": "<discovered sitemap url>",
      "total_urls":  123,
      "urls":        ["https://...", ...],
      "errors":      [],
      "generated_at": "<iso timestamp>"
    }

    Failure:
    {
      "task":        "Sitemap Extraction",
      "status":      "failed",
      "input_url":   "<original input>",
      "base_url":    "<sanitized base or null>",
      "result":      "Sitemap not Found",
      "errors":      ["<reason>"],
      "generated_at": "<iso timestamp>"
    }
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    errors: list[str] = []

    # Step 1 – sanitize
    try:
        base = sanitize_url(raw_url)
    except ValueError as e:
        result = {
            "task":         "Sitemap Extraction",
            "status":       "failed",
            "input_url":    raw_url,
            "base_url":     None,
            "result":       "Sitemap not Found",
            "errors":       [str(e)],
            "generated_at": timestamp,
        }
        _maybe_save(result, "invalid_url", save)
        return result

    # Step 2 – find sitemap
    sitemap_url = find_sitemap_url(base)

    if not sitemap_url:
        result = {
            "task":         "Sitemap Extraction",
            "status":       "failed",
            "input_url":    raw_url,
            "base_url":     base,
            "result":       "Sitemap not Found",
            "errors":       ["No sitemap.xml discovered via robots.txt or common paths."],
            "generated_at": timestamp,
        }
        stem = hostname_to_filename(base)
        _maybe_save(result, stem, save)
        return result

    # Step 3 – parse
    urls: list[str] = []
    parse_sitemap(sitemap_url, urls, set(), errors)

    # Deduplicate, preserve order
    seen: set[str] = set()
    unique: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)

    result = {
        "task":         "Sitemap Extraction",
        "status":       "success",
        "input_url":    raw_url,
        "base_url":     base,
        "sitemap_url":  sitemap_url,
        "total_urls":   len(unique),
        "urls":         unique,
        "errors":       errors,
        "generated_at": timestamp,
    }

    stem = hostname_to_filename(base)
    _maybe_save(result, stem, save)
    return result


def _maybe_save(data: dict, stem: str, save: bool):
    if not save:
        return
    filename = f"{stem}_sitemap.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Saved → {filename}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Extract all sitemap URLs and save as JSON"
    )
    ap.add_argument(
        "url",
        help="Website URL (any format): example.com / www.example.com / https://example.com"
    )
    ap.add_argument(
        "--no-save",
        action="store_true",
        help="Print JSON to stdout instead of saving a file"
    )
    args = ap.parse_args()

    save = not args.no_save
    result = extract_sitemap(args.url, save=save)

    if not save or result["status"] == "failed":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        status = result["status"].upper()
        total  = result.get("total_urls", 0)
        print(f"\n  Status  : {status}")
        print(f"  Base URL: {result['base_url']}")
        print(f"  URLs    : {total}")
        if result.get("errors"):
            print(f"  Warnings: {result['errors']}")


if __name__ == "__main__":
    main()



'''
from sitemap import extract_sitemap
result = extract_sitemap("example.com", save=True)

for run this:  python sitemap.py  oppiwallet.com
'''