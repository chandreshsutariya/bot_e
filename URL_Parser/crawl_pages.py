#this code crawls the pages and extracts the content from the pages. (crawler module)


# this code crawls the pages and extracts the content from the pages (crawler module)

import json
import time
import requests
from bs4 import BeautifulSoup
from readability import Document
from urllib.parse import urljoin
from pathlib import Path
import ftfy  # fixes broken UTF-8 characters

# -----------------------------
# CONFIG
# -----------------------------
INPUT_FILE = "E:/Flask/Playage_Support_Bot/documents_index.json"
OUTPUT_FILE = "E:/Flask/Playage_Support_Bot/new_trail_raw_pages.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (RAG-Bot)"
}

REQUEST_DELAY = 1  # seconds

BLACKLIST_PHRASES = [
    "Confidential Document",
    "Enterprise Management System",
    "For Authorized Personnel Only"
]

# -----------------------------
# TEXT CLEANING HELPERS
# -----------------------------
def fix_encoding(text: str) -> str:
    return ftfy.fix_text(text)


def deduplicate_lines(text: str) -> str:
    seen = set()
    cleaned = []
    for line in text.splitlines():
        line = line.strip()
        if line and line not in seen:
            seen.add(line)
            cleaned.append(line)
    return "\n".join(cleaned)



#footer text remover:
def remove_footer_lines(text: str) -> str:
    cleaned_lines = []

    for line in text.splitlines():
        lower = line.lower()

        is_footer = (
            "professional documentation" in lower and
            "version" in lower and
            "last updated" in lower
        )

        if not is_footer:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def remove_boilerplate(text: str) -> str:
    for phrase in BLACKLIST_PHRASES:
        text = text.replace(phrase, "")
    return text


def normalize_text(text: str) -> str:
    text = fix_encoding(text)
    text = deduplicate_lines(text)
    text = remove_boilerplate(text)
    text = remove_footer_lines(text)
    return text.strip()


# -----------------------------
# CONTENT EXTRACTION
# -----------------------------
def extract_clean_content(html: str, base_url: str):
    """
    Extracts clean text + image URLs and injects image references
    into the relevant section text (production-safe).
    """
    doc = Document(html)
    clean_html = doc.summary(html_partial=True)

    soup = BeautifulSoup(clean_html, "html.parser")

    title = ""

    if soup.title and soup.title.text:
        title = fix_encoding(soup.title.text.strip())

    if not title:
        h1 = soup.find("h1")
        if h1:
            title = fix_encoding(h1.get_text(strip=True))

    sections = []
    current_section = {
        "heading": "Introduction",
        "text": ""
    }

    for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "img"]):

        # -----------------------------
        # HEADINGS
        # -----------------------------
        if tag.name.startswith("h"):
            if current_section["text"].strip():
                current_section["text"] = normalize_text(current_section["text"])
                sections.append(current_section)

            current_section = {
                "heading": fix_encoding(tag.get_text(strip=True)),
                "text": ""
            }

        # -----------------------------
        # IMAGES
        # -----------------------------
        elif tag.name == "img":
            src = tag.get("src")
            if src:
                image_url = urljoin(base_url, src)
                current_section["text"] += (
                    "\nReference screenshot for documentation purposes:\n"
                    f"{image_url}\n"
                )

        # -----------------------------
        # TEXT BLOCKS
        # -----------------------------
        else:
            text = fix_encoding(tag.get_text(" ", strip=True))
            if text:
                current_section["text"] += text + "\n"

    # Final section flush
    if current_section["text"].strip():
        current_section["text"] = normalize_text(current_section["text"])
        sections.append(current_section)

    return {
        "title": title,
        "sections": sections
    }




# -----------------------------
# MAIN EXECUTION
# -----------------------------
def main():
    input_path = Path(INPUT_FILE)
    if not input_path.exists():
        raise FileNotFoundError("documents_index.json not found")

    with open(input_path, "r", encoding="utf-8") as f:
        documents = json.load(f)

    results = []

    for idx, doc in enumerate(documents, start=1):
        url = doc["url"]
        print(f"[{idx}/{len(documents)}] Fetching {url}")

        try:
            response = requests.get(url, headers=HEADERS, timeout=20)
            response.raise_for_status()

            content = extract_clean_content(response.text, url)

            results.append({
                **doc,
                "title": content["title"],
                "sections": content["sections"]
            })

            time.sleep(REQUEST_DELAY)

        except Exception as e:
            print(f"❌ Failed: {url} → {e}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Crawled {len(results)} pages (cleaned + images)")
    print(f"📄 Output saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()