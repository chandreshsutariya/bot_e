"""
Sitemap URL Extractor
━━━━━━━━━━━━━━━━━━━━
Fetches all URLs from a website's sitemap.xml (or sitemap index).
No crawling. No complexity. Just the sitemap.

Usage:
    python sitemap.py https://oppiwallet.com
    python sitemap.py https://oppiwallet.com --save
"""

import xml.etree.ElementTree as ET
import argparse
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# Common sitemap locations to try
SITEMAP_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap/sitemap.xml",
    "/sitemap1.xml",
    "/page-sitemap.xml",
    "/post-sitemap.xml",
    "/robots.txt",          # robots.txt often contains sitemap location
]

NS = {
    "sm":  "http://www.sitemaps.org/schemas/sitemap/0.9",
    "xhtml": "http://www.w3.org/1999/xhtml",
}


def get(url: str) -> requests.Response | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r
    except Exception:
        pass
    return None


def find_sitemap_url(base: str) -> str | None:
    """Check robots.txt first, then try common paths."""
    r = get(f"{base}/robots.txt")
    if r:
        for line in r.text.splitlines():
            if line.lower().startswith("sitemap:"):
                url = line.split(":", 1)[1].strip()
                print(f"  Found in robots.txt: {url}")
                return url

    for path in SITEMAP_PATHS:
        if path == "/robots.txt":
            continue
        url = base.rstrip("/") + path
        r = get(url)
        if r and ("<urlset" in r.text or "<sitemapindex" in r.text):
            print(f"  Found at: {url}")
            return url

    return None


def parse_sitemap(url: str, collected: list, visited: set):
    """Recursively parse sitemap or sitemap index."""
    if url in visited:
        return
    visited.add(url)

    r = get(url)
    if not r:
        print(f"  Could not fetch: {url}")
        return

    try:
        root = ET.fromstring(r.content)
    except ET.ParseError as e:
        print(f"  XML parse error at {url}: {e}")
        return

    tag = root.tag.lower()

    # Sitemap Index → recurse into child sitemaps
    if "sitemapindex" in tag:
        child_urls = [
            loc.text.strip()
            for loc in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
            if loc.text
        ]
        print(f"  Sitemap index with {len(child_urls)} child sitemaps")
        for child_url in child_urls:
            parse_sitemap(child_url, collected, visited)

    # Regular sitemap → collect <loc> entries
    elif "urlset" in tag:
        locs = [
            loc.text.strip()
            for loc in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
            if loc.text
        ]
        collected.extend(locs)
        print(f"  Found {len(locs)} URLs in {url}")


def main():
    ap = argparse.ArgumentParser(description="Extract all URLs from a website sitemap")
    ap.add_argument("url", help="Website base URL, e.g. https://oppiwallet.com")
    ap.add_argument("--save", action="store_true", help="Save URLs to a .txt file")
    args = ap.parse_args()

    base = args.url.rstrip("/")
    # normalize to https if no scheme
    if not base.startswith("http"):
        base = "https://" + base

    print(f"\nLooking for sitemap on: {base}")
    print("-" * 50)

    sitemap_url = find_sitemap_url(base)

    if not sitemap_url:
        print("\n  No sitemap found. The site may not have one.")
        print("  Try running the crawler instead: python crawler.py " + base)
        return

    print("\nParsing sitemap(s)...")
    print("-" * 50)

    urls: list[str] = []
    parse_sitemap(sitemap_url, urls, set())

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)

    print("\n" + "=" * 50)
    print(f"  Total unique URLs found: {len(unique)}")
    print("=" * 50)

    for i, u in enumerate(unique, 1):
        print(f"  [{i:3d}] {u}")

    if args.save:
        from urllib.parse import urlparse
        domain  = urlparse(base).hostname or "site"
        outfile = f"{domain}_urls.txt"
        with open(outfile, "w") as f:
            f.write("\n".join(unique))
        print(f"\n  Saved {len(unique)} URLs to {outfile}")


if __name__ == "__main__":
    main()