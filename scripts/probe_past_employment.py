"""
Probe Crustdata's person-search for past-employment filter support.

We want to know:
  1. Does `experience.employment_details.past.company_name` work as a filter?
  2. Can we request past-employment fields (title, start_date, end_date)?
  3. Can we date-filter on `past.end_date` to get "left in the last 12 months"?
  4. Fallback: if end_date isn't filterable, can we use current.start_date
     as a proxy ("recently joined their next company")?

Run: uv run python scripts/probe_past_employment.py
"""

import asyncio
import json
from datetime import date, timedelta
from typing import Any

from app.services.crustdata import _post

TARGET = "OpenAI"
ONE_YEAR_AGO = (date.today() - timedelta(days=365)).isoformat()


def banner(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def _pick(node: Any, *keys: str) -> Any:
    """Walk dict or list-of-dicts, taking the first dict at each step."""
    for key in keys:
        if isinstance(node, list):
            node = node[0] if node else {}
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def summarize(data: Any, max_rows: int = 3) -> None:
    """Print a compact summary of a person-search response."""
    if not isinstance(data, dict):
        print(json.dumps(data, indent=2)[:1500])
        return
    profiles = data.get("profiles") or data.get("data") or data.get("results") or []
    print(f"top-level keys: {list(data.keys())}  total={data.get('total_count')}")
    print(f"result count:   {len(profiles)}")
    for p in profiles[:max_rows]:
        name = _pick(p, "basic_profile", "name") or "?"
        emp = (p.get("experience") or {}).get("employment_details") or {}
        if isinstance(emp, list):  # API can return a list here
            emp = emp[0] if emp else {}
        cur = emp.get("current") if isinstance(emp, dict) else None
        past = emp.get("past") if isinstance(emp, dict) else None
        if isinstance(cur, list):
            cur = cur[0] if cur else {}
        cur = cur or {}
        past_list = past if isinstance(past, list) else ([past] if past else [])
        cur_str = f"{cur.get('title','?')} @ {cur.get('company_name','?')} (start={cur.get('start_date','?')})"
        print(f"  - {name:30s} | current: {cur_str} | past entries: {len(past_list)}")
        for pe in past_list[:2]:
            if not isinstance(pe, dict):
                continue
            print(
                f"      past: {pe.get('title','?')} @ {pe.get('company_name','?')} "
                f"({pe.get('start_date','?')} → {pe.get('end_date','?')})"
            )


async def try_filter(label: str, body: dict[str, Any]) -> None:
    banner(label)
    print(f"body: {json.dumps(body, indent=2)}")
    try:
        res = await _post("/person/search", body)
        summarize(res)
    except Exception as exc:
        print(f"ERROR: {exc}")


async def main() -> None:
    fields_rich = [
        "basic_profile.name",
        "basic_profile.headline",
        "professional_network_url",
        "experience.employment_details.current.title",
        "experience.employment_details.current.company_name",
        "experience.employment_details.current.start_date",
        "experience.employment_details.past.title",
        "experience.employment_details.past.company_name",
        "experience.employment_details.past.start_date",
        "experience.employment_details.past.end_date",
    ]

    # Probe 1 — can we filter by past.company_name at all?
    await try_filter(
        "PROBE 1 — filter by past.company_name equals",
        {
            "filters": {
                "field": "experience.employment_details.past.company_name",
                "type": "=",
                "value": TARGET,
            },
            "fields": fields_rich,
            "limit": 5,
        },
    )

    # Probe 2 — can we date-filter past.end_date?
    await try_filter(
        f"PROBE 2 — past.company_name = {TARGET!r} AND past.end_date >= {ONE_YEAR_AGO}",
        {
            "filters": {
                "op": "and",
                "conditions": [
                    {
                        "field": "experience.employment_details.past.company_name",
                        "type": "=",
                        "value": TARGET,
                    },
                    {
                        "field": "experience.employment_details.past.end_date",
                        "type": "=>",
                        "value": ONE_YEAR_AGO,
                    },
                ],
            },
            "fields": fields_rich,
            "limit": 5,
        },
    )

    # Probe 3 — recent hires: current.company_name + current.start_date window
    await try_filter(
        f"PROBE 3 — recent hires: current.company_name = {TARGET!r} AND current.start_date >= {ONE_YEAR_AGO}",
        {
            "filters": {
                "op": "and",
                "conditions": [
                    {
                        "field": "experience.employment_details.current.company_name",
                        "type": "=",
                        "value": TARGET,
                    },
                    {
                        "field": "experience.employment_details.current.start_date",
                        "type": "=>",
                        "value": ONE_YEAR_AGO,
                    },
                ],
            },
            "fields": fields_rich,
            "limit": 5,
        },
    )

    # Probe 3b — `recently_changed_jobs` appeared in the supported-fields list.
    # If this is a boolean-ish flag combined with past.company_name, it's a
    # direct "departures in the last N months" query.
    await try_filter(
        f"PROBE 3b — past.company_name = {TARGET!r} AND recently_changed_jobs = true",
        {
            "filters": {
                "op": "and",
                "conditions": [
                    {
                        "field": "experience.employment_details.past.company_name",
                        "type": "=",
                        "value": TARGET,
                    },
                    {"field": "recently_changed_jobs", "type": "=", "value": True},
                ],
            },
            "fields": fields_rich,
            "limit": 5,
        },
    )

    # Probe 3c — non-nested `experience.employment_details.end_date` appeared
    # in the supported-fields list. Try it as a departure date filter.
    await try_filter(
        f"PROBE 3c — past.company_name = {TARGET!r} AND employment_details.end_date >= {ONE_YEAR_AGO}",
        {
            "filters": {
                "op": "and",
                "conditions": [
                    {
                        "field": "experience.employment_details.past.company_name",
                        "type": "=",
                        "value": TARGET,
                    },
                    {
                        "field": "experience.employment_details.end_date",
                        "type": "=>",
                        "value": ONE_YEAR_AGO,
                    },
                ],
            },
            "fields": fields_rich,
            "limit": 5,
        },
    )

    # Probe 4 — fallback: people whose *current* job started <1y ago and whose
    # past includes TARGET. (Works even if past.end_date isn't filterable.)
    await try_filter(
        f"PROBE 4 — fallback departures: past.company_name = {TARGET!r} AND current.start_date >= {ONE_YEAR_AGO}",
        {
            "filters": {
                "op": "and",
                "conditions": [
                    {
                        "field": "experience.employment_details.past.company_name",
                        "type": "=",
                        "value": TARGET,
                    },
                    {
                        "field": "experience.employment_details.current.start_date",
                        "type": "=>",
                        "value": ONE_YEAR_AGO,
                    },
                ],
            },
            "fields": fields_rich,
            "limit": 5,
        },
    )


if __name__ == "__main__":
    asyncio.run(main())
