"""
Probe Crustdata for the three endpoints/fields we plan to use:
  1. Headcount timeseries (by function)
  2. Job listings
  3. LinkedIn company posts

Prints response status + top-level keys for each attempt and writes raw JSON
to probe_fixtures/*.json for inspection.

Run: python probe_apis.py
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx

from app.config import settings

BASE = "https://api.crustdata.com"
HEADERS = {
    "Authorization": f"Bearer {settings.crustdata_api_key}",
    "x-api-version": "2025-11-01",
    "Content-Type": "application/json",
}

DOMAIN = "anthropic.com"
NAME = "Anthropic"

OUT = Path("probe_fixtures")
OUT.mkdir(exist_ok=True)


def save(name: str, payload: object) -> None:
    (OUT / f"{name}.json").write_text(json.dumps(payload, indent=2, default=str)[:200_000])


async def post(client: httpx.AsyncClient, path: str, body: dict) -> tuple[int, object]:
    try:
        r = await client.post(path, json=body)
        try:
            data = r.json()
        except Exception:
            data = {"_raw": r.text[:2000]}
        return r.status_code, data
    except Exception as e:
        return -1, {"_exc": f"{type(e).__name__}: {e}"}


def preview(data: object) -> str:
    if isinstance(data, dict):
        keys = list(data.keys())[:10]
        return f"dict keys={keys}"
    if isinstance(data, list):
        first_keys = list(data[0].keys())[:10] if data and isinstance(data[0], dict) else []
        return f"list len={len(data)} first_keys={first_keys}"
    return f"{type(data).__name__}: {str(data)[:120]}"


async def probe_headcount(client: httpx.AsyncClient) -> None:
    print("\n=== 1. HEADCOUNT TIMESERIES (enrich fields) ===")
    candidates = [
        "headcount_by_facet_timeseries",
        "headcount_timeseries",
        "headcount_by_function",
        "headcount_history",
        "headcount.timeseries",
        "headcount.by_function",
    ]
    for field in candidates:
        status, data = await post(
            client, "/company/enrich", {"domains": [DOMAIN], "fields": [field]}
        )
        if status == 200 and isinstance(data, list) and data:
            matches = data[0].get("matches") if isinstance(data[0], dict) else None
            cd = matches[0].get("company_data") if matches else {}
            cd_keys = list(cd.keys()) if isinstance(cd, dict) else []
            print(f"  field={field!r}: {status} company_data keys={cd_keys[:10]}")
            if cd_keys:
                save(f"headcount_{field.replace('.', '_')}", cd)
        else:
            print(f"  field={field!r}: {status} {preview(data)}")


async def probe_jobs(client: httpx.AsyncClient) -> None:
    print("\n=== 2. JOB LISTINGS ===")
    # Try as enrich fields first
    for field in ["job_listings", "jobs", "job_postings", "open_roles"]:
        status, data = await post(
            client, "/company/enrich", {"domains": [DOMAIN], "fields": [field]}
        )
        if status == 200 and isinstance(data, list) and data:
            cd = (data[0].get("matches") or [{}])[0].get("company_data") or {}
            print(f"  enrich.field={field!r}: {status} keys={list(cd.keys())[:10]}")
            save(f"jobs_{field}_enrich", cd)
        else:
            print(f"  enrich.field={field!r}: {status} {preview(data)}")

    # Try as dedicated endpoints
    for path, body in [
        ("/jobs/search", {"company_domain": DOMAIN, "limit": 5}),
        ("/company/jobs", {"domain": DOMAIN, "limit": 5}),
        ("/company/job_listings", {"domain": DOMAIN, "limit": 5}),
        ("/jobs/company", {"domain": DOMAIN, "limit": 5}),
        ("/company/job_listings/retrieve", {"domains": [DOMAIN], "limit": 5}),
        ("/jobs/listings", {"company_domain": DOMAIN, "limit": 5}),
        ("/company/jobs/search", {"company_domain": DOMAIN, "limit": 5}),
    ]:
        status, data = await post(client, path, body)
        print(f"  {path}: {status} {preview(data)}")
        if status == 200:
            save(f"jobs_ep_{path.replace('/', '_')}", data)


async def probe_linkedin_posts(client: httpx.AsyncClient) -> None:
    print("\n=== 3. LINKEDIN POSTS ===")
    # Try as enrich fields
    for field in ["linkedin_posts", "social_posts", "posts", "company_posts"]:
        status, data = await post(
            client, "/company/enrich", {"domains": [DOMAIN], "fields": [field]}
        )
        if status == 200 and isinstance(data, list) and data:
            cd = (data[0].get("matches") or [{}])[0].get("company_data") or {}
            print(f"  enrich.field={field!r}: {status} keys={list(cd.keys())[:10]}")
            save(f"posts_{field}_enrich", cd)
        else:
            print(f"  enrich.field={field!r}: {status} {preview(data)}")

    # Try dedicated endpoints
    for path, body in [
        ("/company/linkedin_posts", {"domain": DOMAIN, "limit": 5}),
        ("/linkedin/company_posts/retrieve", {"domain": DOMAIN, "limit": 5}),
        ("/linkedin/posts/retrieve", {"company_domain": DOMAIN, "limit": 5}),
        ("/company/posts/retrieve", {"domain": DOMAIN, "limit": 5}),
        ("/company/posts", {"domain": DOMAIN, "limit": 5}),
        ("/linkedin/search/posts", {"company_domain": DOMAIN, "limit": 5}),
        ("/posts/search", {"company_domain": DOMAIN, "limit": 5}),
        ("/linkedin/company/posts", {"domain": DOMAIN, "limit": 5}),
    ]:
        status, data = await post(client, path, body)
        print(f"  {path}: {status} {preview(data)}")
        if status == 200:
            save(f"posts_ep_{path.replace('/', '_')}", data)


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE, headers=HEADERS, timeout=30.0) as client:
        await probe_headcount(client)
        await probe_jobs(client)
        await probe_linkedin_posts(client)
    print(f"\nFixtures saved under {OUT.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())
