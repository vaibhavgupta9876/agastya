"""
In-memory TTL+LRU cache for synthesized briefs.

Keyed by (mode, domain_or_company, role). First viewer pays the ~30s
pipeline; everyone after hits this in <1ms. Lost on redeploy — fine for a
hackathon share loop, swap for SQLite on a Railway volume when it matters.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from threading import Lock

_TTL_SECONDS = 60 * 60 * 24  # 24h
_MAX_ENTRIES = 500


class BriefCache:
    def __init__(self, ttl: int = _TTL_SECONDS, max_entries: int = _MAX_ENTRIES) -> None:
        self._store: OrderedDict[str, tuple[float, dict]] = OrderedDict()
        self._ttl = ttl
        self._max = max_entries
        self._lock = Lock()

    @staticmethod
    def key(mode: str, company: str, role: str, domain: str | None) -> str:
        anchor = (domain or company).strip().lower()
        return f"{mode}::{anchor}::{role.strip().lower()}"

    def get(self, key: str) -> dict | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at < time.time():
                self._store.pop(key, None)
                return None
            self._store.move_to_end(key)
            return value

    def set(self, key: str, value: dict) -> None:
        with self._lock:
            self._store[key] = (time.time() + self._ttl, value)
            self._store.move_to_end(key)
            while len(self._store) > self._max:
                self._store.popitem(last=False)


cache = BriefCache()
