"""mempool.space client with SQLite-backed cache."""

import json
import sqlite3
import time
from pathlib import Path

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_PATH = DATA_DIR / "cache.sqlite"
BASE_URL = "https://mempool.space/api"


class Explorer:
    def __init__(self, db_path: Path = CACHE_PATH, rate_limit_s: float = 0.3):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS http_cache (
                key TEXT PRIMARY KEY,
                body TEXT NOT NULL,
                fetched_at REAL NOT NULL
            )
            """
        )
        self.conn.commit()
        self.rate_limit_s = rate_limit_s
        self.last_fetch = 0.0
        self.session = requests.Session()
        self.session.headers["User-Agent"] = (
            "pizza-day-trace/0.1 (github.com/mnardit/pizza-day-trace)"
        )
        self.stats = {"hits": 0, "misses": 0}

    def _get(self, path: str):
        row = self.conn.execute(
            "SELECT body FROM http_cache WHERE key = ?", (path,)
        ).fetchone()
        if row:
            self.stats["hits"] += 1
            return json.loads(row[0])

        elapsed = time.time() - self.last_fetch
        if elapsed < self.rate_limit_s:
            time.sleep(self.rate_limit_s - elapsed)

        url = BASE_URL + path
        for attempt in range(3):
            try:
                r = self.session.get(url, timeout=30)
                self.last_fetch = time.time()
                if r.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue
                r.raise_for_status()
                break
            except requests.RequestException:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        else:
            raise RuntimeError(f"failed to fetch {path}")

        body = r.text
        data = json.loads(body)
        self.conn.execute(
            "INSERT OR REPLACE INTO http_cache(key, body, fetched_at) VALUES (?, ?, ?)",
            (path, body, time.time()),
        )
        self.conn.commit()
        self.stats["misses"] += 1
        return data

    def tx(self, txid: str):
        return self._get(f"/tx/{txid}")

    def tx_outspends(self, txid: str):
        return self._get(f"/tx/{txid}/outspends")

    def address(self, address: str):
        return self._get(f"/address/{address}")

    def address_txs(self, address: str, last_seen_txid: str | None = None):
        if last_seen_txid:
            return self._get(f"/address/{address}/txs/chain/{last_seen_txid}")
        return self._get(f"/address/{address}/txs")

    def address_all_txs(self, address: str):
        out = []
        last = None
        while True:
            page = self.address_txs(address, last)
            if not page:
                break
            out.extend(page)
            if len(page) < 25:
                break
            last = page[-1]["txid"]
        return out

    def block_hash_at(self, height: int) -> str:
        # mempool returns plain text for this endpoint
        row = self.conn.execute(
            "SELECT body FROM http_cache WHERE key = ?", (f"/block-height/{height}",)
        ).fetchone()
        if row:
            self.stats["hits"] += 1
            return row[0]
        elapsed = __import__("time").time() - self.last_fetch
        if elapsed < self.rate_limit_s:
            __import__("time").sleep(self.rate_limit_s - elapsed)
        r = self.session.get(BASE_URL + f"/block-height/{height}", timeout=30)
        self.last_fetch = __import__("time").time()
        r.raise_for_status()
        body = r.text.strip()
        self.conn.execute(
            "INSERT OR REPLACE INTO http_cache(key, body, fetched_at) VALUES (?, ?, ?)",
            (f"/block-height/{height}", body, __import__("time").time()),
        )
        self.conn.commit()
        self.stats["misses"] += 1
        return body

    def block_txids(self, block_hash: str) -> list[str]:
        return self._get(f"/block/{block_hash}/txids")

    def tx_position_in_block(self, txid: str, block_height: int) -> int:
        """Return 0-based position of `txid` within the block at `block_height`.

        Raises ``TxPositionLookupError`` if the txid is not found in the block's
        canonical txid list. A silent sentinel would let reorg / cache / API
        inconsistencies sort the transaction "to the end of the block" without
        warning, which can reintroduce the same-block parent/child ordering bug
        the topological pass was meant to prevent.
        """
        bh = self.block_hash_at(block_height)
        txids = self.block_txids(bh)
        try:
            return txids.index(txid)
        except ValueError as e:
            raise TxPositionLookupError(
                f"txid {txid} not found in block {block_height} (hash {bh})"
            ) from e


    def chain_tip(self) -> int:
        """Return the current chain tip height. mempool.space returns plain text."""
        return self._get("/blocks/tip/height")


class TxPositionLookupError(LookupError):
    """Raised when a transaction is not in the canonical txid list of its block."""
