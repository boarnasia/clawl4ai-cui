import sqlite3
from datetime import datetime, timezone

DB_PATH = "sqlite.db"


def _conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scrape_history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                url        TEXT    UNIQUE NOT NULL,
                file_path  TEXT    NOT NULL,
                scraped_at TEXT    NOT NULL
            )
        """)


def upsert(url: str, file_path: str) -> str:
    """Insert or update a record. Returns 'inserted' or 'updated'."""
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        existing = conn.execute(
            "SELECT id FROM scrape_history WHERE url = ?", (url,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE scrape_history SET file_path = ?, scraped_at = ? WHERE url = ?",
                (file_path, now, url),
            )
            return "updated"
        conn.execute(
            "INSERT INTO scrape_history (url, file_path, scraped_at) VALUES (?, ?, ?)",
            (url, file_path, now),
        )
        return "inserted"


def list_all() -> list[tuple[str, str, str]]:
    """Returns list of (scraped_at, url, file_path) ordered by scraped_at asc."""
    with _conn() as conn:
        return conn.execute(
            "SELECT scraped_at, url, file_path FROM scrape_history ORDER BY scraped_at ASC"
        ).fetchall()


def get_by_url(url: str) -> tuple[str, str] | None:
    """Returns (url, file_path) or None."""
    with _conn() as conn:
        return conn.execute(
            "SELECT url, file_path FROM scrape_history WHERE url = ?", (url,)
        ).fetchone()


def delete_by_url(url: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM scrape_history WHERE url = ?", (url,))


def delete_all() -> int:
    """Deletes all records. Returns count of deleted rows."""
    with _conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM scrape_history").fetchone()[0]
        conn.execute("DELETE FROM scrape_history")
        return count
