import re
import time

import structlog
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.deep_crawling.filters import FilterChain, URLPatternFilter

_INVALID_CHARS = re.compile(r'[/\s?#&=*"<>|\\:]')


def _sanitize(s: str) -> str:
    return _INVALID_CHARS.sub("_", s)


def build_merged_filename(url: str) -> str:
    bare = re.sub(r"^https?://", "", url).rstrip("/")
    return _sanitize(bare) + ".md"


async def scrape(
    url: str, command: str, log: structlog.stdlib.BoundLogger
) -> list[tuple[str, str]] | bool:
    """
    Recursively crawl all pages under `url` (same prefix, no external links).
    Returns list of (page_url, markdown_text), or False on failure.
    """
    log.info("scrape_start", command=command, url=url)
    start = time.monotonic()

    prefix_pattern = url.rstrip("/") + "/*"
    strategy = BFSDeepCrawlStrategy(
        max_depth=10,
        filter_chain=FilterChain([URLPatternFilter(prefix_pattern)]),
        include_external=False,
    )
    config = CrawlerRunConfig(deep_crawl_strategy=strategy)

    try:
        async with AsyncWebCrawler() as crawler:
            results = await crawler.arun(url=url, config=config)
    except Exception as e:
        log.error("scrape_failed", command=command, url=url, error=str(e))
        return False

    if not results:
        log.warning("scrape_empty", command=command, url=url)
        return False

    pages = []
    for result in results:
        if not result.success:
            continue
        markdown = getattr(result.markdown, "raw_markdown", None) or str(result.markdown or "")
        if not markdown.strip():
            continue
        elapsed = round(time.monotonic() - start, 3)
        log.info("scrape_success", command=command, url=result.url, elapsed_sec=elapsed)
        pages.append((result.url, markdown))

    if not pages:
        log.warning("scrape_empty", command=command, url=url)
        return False

    log.info("scrape_complete", command=command, start_url=url, pages=len(pages),
             elapsed_sec=round(time.monotonic() - start, 3))
    return pages
