import asyncio
import sys
import time
from pathlib import Path

import db
import logger as logger_mod
import scraper

USAGE = """\
Usage:
  python main.py <url>               Scrape URL and save
  python main.py list                List scraped URLs
  python main.py update              Re-scrape all URLs
  python main.py update <url>        Re-scrape a specific URL
  python main.py delete <url>        Delete a URL and its file
  python main.py delete --all        Delete all URLs and files
"""


def _exit_error(msg: str, code: int = 1) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(code)


def cmd_list(log) -> None:
    rows = db.list_all()
    for scraped_at, url, file_path in rows:
        print(f"{scraped_at}\t{url}\t{file_path}")
    log.info("list_output", command="list", count=len(rows))


async def cmd_scrape(url: str, command: str, log) -> None:
    filename = await scraper.scrape(url, command, log)
    if filename is False:
        _exit_error(f"failed to scrape {url}")

    action = db.upsert(url, filename)
    event = "db_insert" if action == "inserted" else "db_upsert"
    log.info(event, command=command, url=url, file_path=filename)


async def cmd_update(args: list[str], log) -> None:
    url = args[1] if len(args) > 1 else None
    if url:
        if not db.get_by_url(url):
            log.error("url_not_found", command="update", url=url)
            _exit_error(f"URL not found in DB: {url}")
        await cmd_scrape(url, "update", log)
    else:
        rows = db.list_all()
        for _, url, _ in rows:
            await cmd_scrape(url, "update", log)


def cmd_delete(args: list[str], log) -> None:
    if len(args) < 2:
        print(USAGE, file=sys.stderr)
        log.error("invalid_args", command="delete", args=args)
        sys.exit(1)

    if args[1] == "--all":
        rows = db.list_all()
        count = len(rows)
        answer = input(f"Delete all {count} entries? [y/N]: ")
        if answer.lower() != "y":
            log.info("delete_all_cancelled", command="delete")
            return

        for _, _, file_path in rows:
            p = Path(f"download/{file_path}")
            if p.exists():
                p.unlink()
        deleted = db.delete_all()
        log.info("db_delete_all", command="delete", count=deleted)
    else:
        url = args[1]
        row = db.get_by_url(url)
        if not row:
            log.error("url_not_found", command="delete", url=url)
            _exit_error(f"URL not found in DB: {url}")

        _, file_path = row
        p = Path(f"download/{file_path}")
        if p.exists():
            p.unlink()
        db.delete_by_url(url)
        log.info("db_delete", command="delete", url=url, file_path=file_path)


async def main() -> None:
    db.init_db()
    log = logger_mod.setup_logger()

    args = sys.argv[1:]

    if not args:
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    cmd = args[0]
    start = time.monotonic()

    if cmd == "list":
        log.info("command_start", command="list", args=args)
        cmd_list(log)

    elif cmd == "update":
        log.info("command_start", command="update", args=args)
        await cmd_update(args, log)

    elif cmd == "delete":
        log.info("command_start", command="delete", args=args)
        cmd_delete(args, log)

    elif cmd.startswith("http://") or cmd.startswith("https://"):
        log.info("command_start", command="scrape", args=args)
        await cmd_scrape(cmd, "scrape", log)

    else:
        log.error("invalid_args", command="unknown", args=args)
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    cmd_name = "scrape" if cmd.startswith("http") else cmd
    log.info("command_end", command=cmd_name, elapsed_sec=round(time.monotonic() - start, 3), exit_code=0)


if __name__ == "__main__":
    asyncio.run(main())
