"""SQLite caching layer for Steam API responses.

Stores cache entries by endpoint and appid. Optional TTL (time-to-live) in seconds.
"""
import sqlite3
import json
import time
from typing import Optional


class SteamCache:
    def __init__(self, db_path: str = "steam_cache.db", ttl_seconds: int = 604800):
        """Initialize cache with optional TTL (default 7 days)."""
        self.db_path = db_path
        self.ttl_seconds = ttl_seconds
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    endpoint TEXT NOT NULL,
                    appid INTEGER NOT NULL,
                    data TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    PRIMARY KEY (endpoint, appid)
                )
            """)
            conn.commit()

    def get(self, endpoint: str, appid: int) -> Optional[dict]:
        """Retrieve cached data if it exists and is not expired."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT data, timestamp FROM cache WHERE endpoint = ? AND appid = ?",
                (endpoint, appid)
            )
            row = cursor.fetchone()
            if not row:
                return None
            data_str, ts = row
            # Check if expired
            if time.time() - ts > self.ttl_seconds:
                # Delete expired entry
                conn.execute("DELETE FROM cache WHERE endpoint = ? AND appid = ?", (endpoint, appid))
                conn.commit()
                return None
            return json.loads(data_str)

    def set(self, endpoint: str, appid: int, data: dict):
        """Store data in cache."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (endpoint, appid, data, timestamp) VALUES (?, ?, ?, ?)",
                (endpoint, appid, json.dumps(data), time.time())
            )
            conn.commit()

    def clear(self):
        """Clear all cache entries."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache")
            conn.commit()

    def get_stats(self) -> dict:
        """Get cache statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM cache")
            count = cursor.fetchone()[0]
            cursor = conn.execute("SELECT endpoint, COUNT(*) as cnt FROM cache GROUP BY endpoint")
            by_endpoint = {row[0]: row[1] for row in cursor.fetchall()}
        return {"total": count, "by_endpoint": by_endpoint}
