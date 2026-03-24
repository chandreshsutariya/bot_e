import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json

visited = set()
results = []


def crawl(url, domain):
    if url in visited:
        return

    visited.add(url)

    try:
        response = requests.get(url, timeout=5)
        soup = BeautifulSoup(response.text, "html.parser")

        results.append(url)

        for link in soup.find_all("a", href=True):
            href = link["href"]
            full_url = urljoin(url, href)

            parsed = urlparse(full_url)

            # only crawl same domain
            if parsed.netloc == domain:
                clean_url = parsed.scheme + "://" + parsed.netloc + parsed.path

                if clean_url not in visited:
                    crawl(clean_url, domain)

    except Exception:
        print("Failed:", url)


def group_by_module(urls):
    modules = {}

    for url in urls:
        path = urlparse(url).path.strip("/")
        parts = path.split("/")

        # example: en/bo , en/cms
        if len(parts) >= 2:
            module = f"{parts[0]}/{parts[1]}"
        else:
            module = "root"

        modules.setdefault(module, []).append(url)

    return modules


def generate_sitemap(start_url):

    domain = urlparse(start_url).netloc

    print("Crawling started...")
    crawl(start_url, domain)

    print("Total URLs found:", len(results))

    modules = group_by_module(results)

    data = {
        "total_urls": len(results),
        "modules": modules
    }

    with open("modules_sitemap.json", "w") as f:
        json.dump(data, f, indent=2)

    print("Saved to modules_sitemap.json")


# START URL
generate_sitemap("https://userguide.playagegaming.tech/en/bo")