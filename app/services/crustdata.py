"""
Crustdata API client.

Each method maps 1:1 to a Crustdata endpoint. Methods return the raw parsed
JSON so callers can extract what they need without opinionated field selection.
Raises CrustdataError on any non-2xx response.
"""

from typing import Any

import httpx

from app.config import settings

_BASE_URL = "https://api.crustdata.com"
_API_VERSION = "2025-11-01"


class CrustdataError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(f"Crustdata {status}: {detail}")


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={
            "Authorization": f"Bearer {settings.crustdata_api_key}",
            "x-api-version": _API_VERSION,
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


async def _post(path: str, body: dict[str, Any]) -> Any:
    async with _client() as client:
        response = await client.post(path, json=body)
        if response.status_code >= 400:
            try:
                data = response.json()
                detail = data.get("description") or data.get("reason") or response.text
            except Exception:
                detail = response.text
            raise CrustdataError(response.status_code, detail)
        return response.json()


# ---------------------------------------------------------------------------
# Company
# ---------------------------------------------------------------------------


async def identify_company(name: str) -> Any:
    """Resolve a company name to a structured company record."""
    return await _post("/company/identify", {"names": [name]})


async def enrich_company(domain: str) -> Any:
    """
    Fetch the full company profile for a given domain.
    Returns funding, headcount, industries, tech stack, customers, etc.
    """
    return await _post("/company/enrich", {"domains": [domain]})


async def search_companies(filters: list[dict[str, Any]], limit: int = 10) -> Any:
    """Filter-based company search. Useful for finding similar companies."""
    return await _post("/company/search", {"filters": filters, "limit": limit})


# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------


async def search_people(
    company_domain: str,
    titles: list[str] | None = None,
    limit: int = 10,
) -> Any:
    """
    Find people at a company. Optionally filter by job title keywords.

    `titles` values are matched as substrings against current_title, e.g.
    ["engineering manager", "vp engineering", "cto"] to find eng leadership.
    """
    filters: list[dict[str, Any]] = [
        {"field": "current_company.domain", "type": "equals", "value": company_domain}
    ]
    if titles:
        filters.append(
            {"field": "current_title", "type": "in_list", "value": titles}
        )
    return await _post("/person/search", {"filters": filters, "limit": limit})


async def enrich_person(linkedin_url: str) -> Any:
    """Fetch cached profile data for a person by their LinkedIn URL."""
    return await _post(
        "/person/enrich",
        {"professional_network_profile_urls": [linkedin_url]},
    )


async def enrich_person_live(linkedin_url: str) -> Any:
    """Fetch a fresh, real-time profile from the web for a given LinkedIn URL."""
    return await _post(
        "/person/professional_network/enrich/live",
        {"professional_network_profile_urls": [linkedin_url]},
    )


async def search_people_live(
    company_domain: str,
    titles: list[str] | None = None,
    limit: int = 10,
) -> Any:
    """Real-time people search — slower but more current than the cached endpoint."""
    filters: list[dict[str, Any]] = [
        {"field": "current_company.domain", "type": "equals", "value": company_domain}
    ]
    if titles:
        filters.append(
            {"field": "current_title", "type": "in_list", "value": titles}
        )
    return await _post(
        "/person/professional_network/search/live",
        {"filters": filters, "limit": limit},
    )


# ---------------------------------------------------------------------------
# Web
# ---------------------------------------------------------------------------


async def web_search(query: str, limit: int = 5) -> Any:
    """Search the live web. Use for recent news, press, product announcements."""
    return await _post("/web/search/live", {"query": query, "limit": limit})


async def web_enrich(url: str) -> Any:
    """Extract and return the full text content of a web page."""
    return await _post("/web/enrich/live", {"url": url})
