"""
Scrapy Crawler for oppiwallet.com
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Install:
    pip install scrapy

Run:
    # Basic crawl - prints all URLs
    scrapy runspider oppiwallet_spider.py

    # Save to JSON
    scrapy runspider oppiwallet_spider.py -o output.json

    # Save to CSV
    scrapy runspider oppiwallet_spider.py -o output.csv

    # Control depth
    scrapy runspider oppiwallet_spider.py -s DEPTH_LIMIT=3

    # Silent mode (no scrapy logs)
    scrapy runspider oppiwallet_spider.py -s LOG_LEVEL=WARNING
"""

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule
from urllib.parse import urlparse


# ══════════════════════════════════════════════════════════
# OPTION 1: SitemapSpider (RECOMMENDED — uses sitemap.xml)
# The smartest approach — Scrapy has this built-in
# ══════════════════════════════════════════════════════════

class OppiSitemapSpider(scrapy.Spider):
    """
    Uses sitemap.xml — same approach as our sitemap.py but now
    with Scrapy's full pipeline: items, pipelines, middlewares.
    """
    name = "oppi_sitemap"

    # Scrapy auto-discovers /sitemap.xml, /robots.txt sitemap entries
    sitemap_urls = ["https://oppiwallet.com/sitemap.xml"]

    # Only crawl English pages (remove filter to get all languages)
    sitemap_rules = [
        ("/en/", "parse_page"),
    ]

    custom_settings = {
        "DEPTH_LIMIT":          5,
        "CONCURRENT_REQUESTS":  8,
        "DOWNLOAD_DELAY":       0.3,        # polite delay
        "ROBOTSTXT_OBEY":       True,       # respect robots.txt
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        # Auto-throttle: slows down if server is overloaded
        "AUTOTHROTTLE_ENABLED":       True,
        "AUTOTHROTTLE_START_DELAY":   0.5,
        "AUTOTHROTTLE_MAX_DELAY":     3.0,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 2.0,
    }

    def parse_page(self, response):
        """Extract structured data from each page."""
        yield {
            "url":         response.url,
            "title":       response.css("title::text").get("").strip(),
            "h1":          response.css("h1::text").get("").strip(),
            "description": response.css("meta[name=description]::attr(content)").get("").strip(),
            "status":      response.status,
            "depth":       response.meta.get("depth", 0),
        }


# ══════════════════════════════════════════════════════════
# OPTION 2: CrawlSpider (full BFS crawl with rules)
# Use when there's no sitemap
# ══════════════════════════════════════════════════════════

class OppiCrawlSpider(CrawlSpider):
    """
    Full BFS crawler using Scrapy's CrawlSpider.
    Rules define what links to follow — no manual queue management needed.
    Scrapy handles: deduplication, politeness, retries, redirects — all built-in.
    """
    name = "oppi_crawl"
    allowed_domains = ["oppiwallet.com"]
    start_urls      = ["https://oppiwallet.com/en"]

    # Rules replace all your manual BFS queue logic
    rules = (
        # Follow all internal links AND parse them
        Rule(
            LinkExtractor(allow_domains=["oppiwallet.com"]),
            callback="parse_page",
            follow=True,        # keep crawling from each page
        ),
    )

    custom_settings = {
        "DEPTH_LIMIT":         5,
        "CONCURRENT_REQUESTS": 8,
        "DOWNLOAD_DELAY":      0.3,
        "ROBOTSTXT_OBEY":      True,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "AUTOTHROTTLE_ENABLED": True,
    }

    def parse_page(self, response):
        yield {
            "url":         response.url,
            "title":       response.css("title::text").get("").strip(),
            "h1":          response.css("h1::text").get("").strip(),
            "description": response.css("meta[name=description]::attr(content)").get("").strip(),
            "links_count": len(response.css("a[href]")),
            "status":      response.status,
            "depth":       response.meta.get("depth", 0),
        }


# ══════════════════════════════════════════════════════════
# OPTION 3: Run programmatically (no CLI needed)
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    # Choose spider:  "sitemap" (default) or "crawl"
    mode = sys.argv[1] if len(sys.argv) > 1 else "sitemap"

    spider = OppiSitemapSpider if mode == "sitemap" else OppiCrawlSpider

    process = CrawlerProcess(settings={
        "FEEDS": {
            "output.json": {"format": "json", "overwrite": True},
        },
        "LOG_LEVEL": "INFO",
    })

    process.crawl(spider)
    process.start()
    print("\nDone! Results saved to output.json")