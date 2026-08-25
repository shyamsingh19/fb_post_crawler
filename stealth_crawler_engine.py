import argparse
import asyncio
import logging
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from typing import Any
import dotenv
import httpx

dotenv.load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s - %(levelname)s - %(message)s",
)

SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY")
SCRAPER_DATASET_ID = os.getenv("SCRAPER_DATASET_ID")


@dataclass(frozen=True)
class PostDTO:
    post_id: str
    group_url: str
    author_name: str
    post_text: str
    post_url: str
    timestamp: str
    extracted_price: float | None = None
    extracted_rooms: float | None = None


class TextParsingEngine:
    """Extract common rental listing values from post text."""

    _PRICE_PATTERN = re.compile(
        r"(?:[\$\u20b9])?\s*(\d{1,3}(?:,\d{3})+|\d{3,6})"
        r"\s*(?:USD|INR|\$|\u20b9|dollars|/month)?",
        re.IGNORECASE,
    )
    _ROOM_PATTERN = re.compile(
        r"(\d(?:\.5)?)\s*(?:bhk|bedroom|bed|rooms?|rk)\b", re.IGNORECASE
    )

    @classmethod
    def extract_price(cls, text: str) -> float | None:
        for match in cls._PRICE_PATTERN.finditer(text):
            value = float(match.group(1).replace(",", ""))
            if 100 <= value <= 500_000:
                return value
        return None

    @classmethod
    def extract_rooms(cls, text: str) -> float | None:
        match = cls._ROOM_PATTERN.search(text)
        return float(match.group(1)) if match else None


class DatabaseStorageManager:
    """Initializes the normalized schema and persists posts idempotently."""

    def __init__(self, db_path: str = "facebook_crawled_data.db"):
        self.db_path = db_path
        logging.debug("[database:init] Opening database: %s", db_path)
        self._init_db()
        logging.debug("[database:init] Schema and indexes are ready")

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS facebook_posts (
                    post_id TEXT PRIMARY KEY,
                    group_url TEXT NOT NULL,
                    author_name TEXT,
                    post_text TEXT,
                    extracted_price REAL,
                    extracted_rooms REAL,
                    post_url TEXT NOT NULL,
                    timestamp TEXT,
                    scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_posts_price
                    ON facebook_posts(extracted_price);
                CREATE INDEX IF NOT EXISTS idx_posts_group
                    ON facebook_posts(group_url);
                """)

    def save_post(self, post: PostDTO) -> None:
        logging.debug("[database:write] Saving post_id=%s", post.post_id)
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO facebook_posts (
                    post_id, group_url, author_name, post_text,
                    extracted_price, extracted_rooms, post_url, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(post_id) DO UPDATE SET
                    author_name = excluded.author_name,
                    post_text = excluded.post_text,
                    extracted_price = excluded.extracted_price,
                    extracted_rooms = excluded.extracted_rooms,
                    post_url = excluded.post_url,
                    timestamp = excluded.timestamp
                """,
                (
                    post.post_id,
                    post.group_url,
                    post.author_name,
                    post.post_text,
                    post.extracted_price,
                    post.extracted_rooms,
                    post.post_url,
                    post.timestamp,
                ),
            )
            logging.debug("[database:write] Saved post_id=%s", post.post_id)


def print_database_posts(db_path: str, limit: int | None = None) -> None:
    query = """
        SELECT post_id, post_text, scraped_at
        FROM facebook_posts
        ORDER BY scraped_at, rowid
    """
    parameters: tuple[int, ...] = ()
    if limit is not None:
        query += " LIMIT ?"
        parameters = (limit,)

    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as connection:
            rows = connection.execute(query, parameters).fetchall()
    except sqlite3.Error as error:
        raise SystemExit(f"Could not read database '{db_path}': {error}") from error

    if not rows:
        print("No posts found.")
        return
    for post_id, post_text, scraped_at in rows:
        print(f"\n--- {post_id} ({scraped_at}) ---\n{post_text}")


class ManagedAPIFacebookCrawler:

    def __init__(
        self,
        api_key: str,
        db_manager: DatabaseStorageManager,
        endpoint: str = "https://api.brightdata.com/datasets/v3/scrape",
        dataset_id: str | None = None,
        poll_interval: float = 10.0,
        max_wait: float = 600.0,
    ):
        if not api_key:
            raise ValueError("An API key is required")
        self.api_key = api_key
        self.db_manager = db_manager
        self.poll_interval = poll_interval
        self.max_wait = max_wait
        self.dataset_id = dataset_id or os.getenv("SCRAPER_DATASET_ID")
        if not self.dataset_id:
            raise ValueError("SCRAPER_DATASET_ID must be set")
        # Include dataset_id and flags in the URL query params
        self.endpoint = (
            f"{endpoint}?dataset_id={self.dataset_id}&notify=false&include_errors=true"
        )
        logging.debug(
            "[crawler:init] endpoint=%s dataset_id=%s api_key=present",
            endpoint,
            self.dataset_id,
        )

    @staticmethod
    def _records(payload: dict[str, Any]) -> list[dict[str, Any]]:
        records = payload.get("snapshot_data") or payload.get("data") or []
        return [record for record in records if isinstance(record, dict)]

    async def _wait_for_snapshot(
        self, client: httpx.AsyncClient, snapshot_id: str, headers: dict[str, str]
    ) -> list[dict[str, Any]]:
        progress_url = (
            "https://api.brightdata.com/datasets/v3/progress/" f"{snapshot_id}"
        )
        download_url = (
            "https://api.brightdata.com/datasets/v3/snapshot/" f"{snapshot_id}"
        )
        deadline = time.monotonic() + self.max_wait
        attempt = 0

        while time.monotonic() < deadline:
            attempt += 1
            logging.info(
                "[stage 3/6] Checking snapshot progress: attempt=%d snapshot_id=%s",
                attempt,
                snapshot_id,
            )
            progress_response = await client.get(progress_url, headers=headers)
            logging.debug(
                "[stage 3/6] Progress response status=%d body=%s",
                progress_response.status_code,
                progress_response.text[:1000],
            )
            progress_response.raise_for_status()
            progress = progress_response.json()
            status = str(progress.get("status") or progress.get("state") or "").lower()
            logging.info("[stage 3/6] Snapshot status=%s", status or "unknown")

            if status in {"ready", "completed", "complete", "succeeded", "success"}:
                logging.info("[stage 4/6] Downloading completed snapshot")
                download_response = await client.get(download_url, headers=headers)
                logging.debug(
                    "[stage 4/6] Snapshot response status=%d bytes=%d",
                    download_response.status_code,
                    len(download_response.content),
                )
                download_response.raise_for_status()
                payload = download_response.json()
                records = payload if isinstance(payload, list) else self._records(payload)
                logging.info("[stage 4/6] Downloaded %d snapshot records", len(records))
                return records

            if status in {"failed", "error", "cancelled", "canceled"}:
                raise RuntimeError(f"Snapshot {snapshot_id} failed: {progress}")

            remaining = max(0, int(deadline - time.monotonic()))
            logging.info(
                "[stage 3/6] Snapshot still processing; retrying in %.0fs (max wait remaining %ds)",
                self.poll_interval,
                remaining,
            )
            await asyncio.sleep(self.poll_interval)

        raise TimeoutError(
            f"Snapshot {snapshot_id} did not finish within {self.max_wait:.0f} seconds"
        )

    async def fetch_group_posts(self, group_url: str, limit: int = 50) -> int:
        started_at = time.monotonic()
        logging.info(
            "[stage 1/5] Starting fetch: group_url=%s limit=%d", group_url, limit
        )
        payload = {"input": [{"url": group_url, "num_of_posts": limit}]}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        logging.debug("[stage 2/5] Sending API request with payload=%s", payload)
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    self.endpoint, headers=headers, json=payload
                )
        except httpx.TimeoutException:
            logging.exception("[stage 2/5] API request timed out after 120 seconds")
            raise
        except httpx.RequestError:
            logging.exception("[stage 2/5] API request failed before receiving a response")
            raise

        logging.info(
            "[stage 3/6] API response received: status=%d elapsed=%.1fs",
            response.status_code,
            time.monotonic() - started_at,
        )
        logging.debug("[stage 3/6] API response body: %s", response.text[:2000])
        if response.is_error:
            logging.error(
                "[stage 3/6] API error body: %s", response.text[:2000]
            )
            response.raise_for_status()
        response_payload = response.json()
        async with httpx.AsyncClient(timeout=120.0) as client:
            if response.status_code == httpx.codes.ACCEPTED:
                snapshot_id = response_payload.get("snapshot_id")
                if not snapshot_id:
                    raise RuntimeError("Async API response did not include snapshot_id")
                logging.warning(
                    "[stage 3/6] API accepted snapshot_id=%s; waiting for completion",
                    snapshot_id,
                )
                records = await self._wait_for_snapshot(client, snapshot_id, headers)
            else:
                records = response_payload

        if response.status_code == httpx.codes.ACCEPTED:
            logging.warning(
                "[stage 4/6] Async snapshot downloaded; continuing with record parsing"
            )
        if isinstance(records, dict):
            records = self._records(records)
        if not isinstance(records, list):
            raise TypeError(f"Expected API records list, received {type(records).__name__}")
        logging.info("[stage 5/6] Parsed %d API records", len(records))
        if not records:
            logging.warning(
                "[stage 5/6] No records were returned; verify the dataset and group access"
            )

        saved_count = 0
        for index, item in enumerate(records, start=1):
            if not isinstance(item, dict):
                logging.warning("[stage 6/6] Skipping record %d: expected object", index)
                continue
            text = str(item.get("content") or item.get("text") or "").strip()
            post_url = str(item.get("url") or group_url)
            post_id = str(item.get("post_id") or item.get("id") or post_url)
            post = PostDTO(
                post_id=post_id,
                group_url=group_url,
                author_name=str(
                    item.get("user_username_raw")
                    or item.get("author")
                    or "Unknown Author"
                ),
                post_text=text,
                post_url=post_url,
                timestamp=str(item.get("date_posted") or item.get("timestamp") or ""),
                extracted_price=TextParsingEngine.extract_price(text),
                extracted_rooms=TextParsingEngine.extract_rooms(text),
            )
            self.db_manager.save_post(post)
            saved_count += 1
            logging.debug(
                "[stage 6/6] Processed record %d/%d post_id=%s text_length=%d price=%s rooms=%s",
                index,
                len(records),
                post_id,
                len(text),
                post.extracted_price,
                post.extracted_rooms,
            )

        logging.info(
            "[complete] Persisted %d/%d records in %.1fs for %s",
            saved_count,
            len(records),
            time.monotonic() - started_at,
            group_url,
        )
        return saved_count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch or view saved Facebook posts.")
    parser.add_argument("--view-db", metavar="PATH", help="Print saved posts and exit.")
    parser.add_argument("--limit", type=int, help="Maximum posts to fetch or print.")
    parser.add_argument("--group-url", help="Public Facebook group URL to fetch.")
    parser.add_argument(
        "--db", default="facebook_crawled_data.db", help="SQLite database path."
    )
    return parser


async def run(args: argparse.Namespace) -> None:
    logging.debug("[startup] Parsed arguments: %s", args)
    if args.view_db:
        logging.info("[stage 1/2] Reading database: %s", args.view_db)
        print_database_posts(args.view_db, args.limit)
        logging.info("[complete] Database read finished")
        return
    if not args.group_url:
        raise SystemExit("--group-url is required unless --view-db is used")
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be greater than zero")
    crawler = ManagedAPIFacebookCrawler(
        SCRAPER_API_KEY or "", DatabaseStorageManager(args.db)
    )
    logging.info("[startup] Configuration loaded; API key present=%s", bool(SCRAPER_API_KEY))
    await crawler.fetch_group_posts(args.group_url, args.limit or 50)


if __name__ == "__main__":
    asyncio.run(run(build_parser().parse_args()))
