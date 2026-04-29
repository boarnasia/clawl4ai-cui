import re
import time
from pathlib import Path

import structlog
from crawl4ai import AsyncWebCrawler

_INVALID_CHARS = re.compile(r'[/\s?#&=*"<>|\\:]')


def _sanitize(s: str) -> str:
    return _INVALID_CHARS.sub("_", s)


def build_filename(url: str, title: str) -> str:
    bare = re.sub(r"^https?://", "", url).rstrip("/")
    url_part = _sanitize(bare)
    title_part = _sanitize(title)
    return f"{url_part}--{title_part}.md"


async def scrape(url: str, command: str, log: structlog.stdlib.BoundLogger) -> bool:
    Path("download").mkdir(exist_ok=True)
    log.info("scrape_start", command=command, url=url)
    start = time.monotonic()

    try:
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url)
    except Exception as e:
        log.error("scrape_failed", command=command, url=url, error=str(e))
        return False

    markdown = getattr(result.markdown, "raw_markdown", None) or str(result.markdown or "")
    if not markdown.strip():
        log.warning("scrape_empty", command=command, url=url)
        return False

    title = (result.metadata or {}).get("title") or "untitled"
    filename = build_filename(url, title)
    Path(f"download/{filename}").write_text(markdown, encoding="utf-8")

    elapsed = round(time.monotonic() - start, 3)
    log.info("scrape_success", command=command, url=url, file_path=filename, elapsed_sec=elapsed)
    return filename
