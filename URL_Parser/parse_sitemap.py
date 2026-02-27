#this code converts sitemap json to document indexing in tree strucure json.

import json
from urllib.parse import urlparse
from pathlib import Path


# -----------------------------
# CONFIG
# -----------------------------
INPUT_FILE = "E:/Flask/Playage_Support_Bot/backoffice_sitemap.json"
OUTPUT_FILE = "E:/Flask/Playage_Support_Bot/documents_index.json"


# -----------------------------
# URL PARSING LOGIC
# -----------------------------
def parse_url_metadata(url: str):
    """
    Example URL:
    https://userguide.playagegaming.tech/en/bo/player-management/3-1-1/

    Parsed path:
    ['en', 'bo', 'player-management', '3-1-1']
    """

    parsed = urlparse(url)
    path_parts = parsed.path.strip("/").split("/")

    # Safety checks
    module = path_parts[1] if len(path_parts) > 1 else None
    category = path_parts[2] if len(path_parts) > 2 else None
    topic_id = path_parts[3] if len(path_parts) > 3 else None

    # Hierarchy level (bo = level 1, category = level 2, topic = level 3)
    level = len(path_parts) - 2 if len(path_parts) >= 2 else 0

    # Build doc_id
    if category and topic_id:
        doc_id = f"{category}/{topic_id}"
    elif category:
        doc_id = category
    else:
        doc_id = "root"

    return {
        "doc_id": doc_id,
        "module": module,
        "category": category,
        "topic_id": topic_id,
        "level": level
    }


# -----------------------------
# MAIN EXECUTION
# -----------------------------
def main():
    input_path = Path(INPUT_FILE)

    if not input_path.exists():
        raise FileNotFoundError(f"❌ {INPUT_FILE} not found")

    # Load sitemap JSON
    with open(input_path, "r", encoding="utf-8") as f:
        sitemap = json.load(f)

    urls = sitemap["urlset"]["url"]
    documents = []

    for entry in urls:
        url = entry["loc"]
        priority = float(entry.get("priority", 0.5))
        lastmod = entry.get("lastmod")

        meta = parse_url_metadata(url)

        document = {
            "doc_id": meta["doc_id"],
            "url": url,
            "module": meta["module"],
            "category": meta["category"],
            "topic_id": meta["topic_id"],
            "level": meta["level"],
            "priority": priority,
            "lastmod": lastmod
        }

        documents.append(document)

    # Save structured index
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(documents, f, indent=2, ensure_ascii=False)

    print(f"✅ Parsed {len(documents)} URLs")
    print(f"📄 Output saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()