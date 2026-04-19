"""
Prewarm cache for the role-independent half of the dossier pipeline.

When the user picks a company from the typeahead, the frontend fires
POST /prewarm to kick off Crustdata enrich + web searches + hires/departures
in the background. By the time they type the role and submit, this work
is done and cached — saving 3-8s off the first-submit latency.

Design:
- Single in-memory dict keyed by domain.
- In-flight lookups share an `asyncio.Future` so concurrent requests
  (e.g. prewarm racing with submit) don't double-fetch.
- 10-minute TTL — Crustdata responses don't move fast, but memory is cheap
  and staleness matters more than hit rate.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from app.services.crustdata import (
    enrich_company,
    recent_departures,
    recent_hires,
    search_people,
    web_search,
)

_TTL_SECONDS = 60 * 10


@dataclass
class PrewarmBundle:
    """The role-independent portion of the dossier fan-out."""

    resolved_name: str
    domain: str
    enrich_resp: Any = None
    customer_results: list[dict[str, Any]] = field(default_factory=list)
    insider_results: list[dict[str, Any]] = field(default_factory=list)
    hires_resp: Any = None
    departures_resp: Any = None
    search_resp: Any = None  # company-wide people search (playbook only)
    strategy_web_results: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = 0.0


def _customer_queries(resolved_name: str, domain: str) -> list[str]:
    return [
        f"{resolved_name} customer case study",
        f"site:{domain} customers",
        f"site:{domain} case studies",
        f'"{resolved_name}" powers OR trusts OR chose',
    ]


def _insider_queries(resolved_name: str) -> list[str]:
    return [
        f'site:glassdoor.com "{resolved_name}"',
        f'site:teamblind.com "{resolved_name}"',
        f'"{resolved_name} CEO" interview OR podcast',
    ]


async def _fetch(resolved_name: str, domain: str) -> PrewarmBundle:
    bundle = PrewarmBundle(resolved_name=resolved_name, domain=domain)

    customer_tasks = [asyncio.create_task(web_search(q, limit=5)) for q in _customer_queries(resolved_name, domain)]
    insider_tasks = [asyncio.create_task(web_search(q, limit=5)) for q in _insider_queries(resolved_name)]
    strategy_task = asyncio.create_task(
        web_search(f"{resolved_name} strategy customers product launch", limit=5)
    )

    enrich_task = asyncio.create_task(enrich_company(domain))
    hires_task = asyncio.create_task(recent_hires(resolved_name, days=365, limit=25))
    departures_task = asyncio.create_task(recent_departures(resolved_name, limit=50))
    search_task = asyncio.create_task(search_people(resolved_name, limit=30))

    results = await asyncio.gather(
        enrich_task, hires_task, departures_task, search_task, strategy_task,
        *customer_tasks, *insider_tasks,
        return_exceptions=True,
    )
    enrich_resp, hires_resp, departures_resp, search_resp, strategy_resp = results[:5]
    customer_resps = results[5 : 5 + len(customer_tasks)]
    insider_resps = results[5 + len(customer_tasks) : 5 + len(customer_tasks) + len(insider_tasks)]

    bundle.enrich_resp = enrich_resp if not isinstance(enrich_resp, Exception) else None
    bundle.hires_resp = hires_resp if not isinstance(hires_resp, Exception) else None
    bundle.departures_resp = departures_resp if not isinstance(departures_resp, Exception) else None
    bundle.search_resp = search_resp if not isinstance(search_resp, Exception) else None
    if isinstance(strategy_resp, dict):
        bundle.strategy_web_results = strategy_resp.get("results") or []
    for r in customer_resps:
        if isinstance(r, dict):
            bundle.customer_results.extend(r.get("results") or [])
    for r in insider_resps:
        if isinstance(r, dict):
            bundle.insider_results.extend(r.get("results") or [])

    bundle.created_at = time.time()
    return bundle


class _PrewarmRegistry:
    def __init__(self) -> None:
        self._cache: dict[str, PrewarmBundle] = {}
        self._inflight: dict[str, asyncio.Future[PrewarmBundle]] = {}
        self._lock = asyncio.Lock()

    async def get_or_fetch(self, resolved_name: str, domain: str) -> PrewarmBundle:
        """Return a fresh prewarm bundle, sharing in-flight work across callers."""
        key = domain.lower()
        async with self._lock:
            cached = self._cache.get(key)
            if cached and time.time() - cached.created_at < _TTL_SECONDS:
                return cached
            future = self._inflight.get(key)
            if future is not None:
                return await future
            future = asyncio.get_event_loop().create_future()
            self._inflight[key] = future

        try:
            bundle = await _fetch(resolved_name, domain)
            self._cache[key] = bundle
            future.set_result(bundle)
            return bundle
        except Exception as e:
            future.set_exception(e)
            raise
        finally:
            self._inflight.pop(key, None)

    def prewarm_in_background(self, resolved_name: str, domain: str) -> None:
        """Fire-and-forget: caller doesn't wait for the bundle."""
        asyncio.create_task(self._silent_prewarm(resolved_name, domain))

    async def _silent_prewarm(self, resolved_name: str, domain: str) -> None:
        try:
            await self.get_or_fetch(resolved_name, domain)
        except Exception:
            # Prewarm is best-effort. If it fails, the real submit will retry.
            pass


registry = _PrewarmRegistry()
