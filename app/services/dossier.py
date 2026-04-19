"""
Dossier assembly.

Given a company name + role, orchestrate parallel Crustdata calls and return
a normalized `RawDossier` ready for GPT-5 synthesis.

Design notes:
- Primary people source is `company_data.people` (founders, decision_makers,
  cxos) embedded in the enrich response — richer and cheaper than a separate
  person-search call.
- We fan out enrich + web_search in parallel, then optionally supplement with
  a company-wide person search for broader team context.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.models.schemas import CompanySnapshot, PersonCard, RawDossier, Signal
from app.services.crustdata import (
    CrustdataError,
    enrich_company,
    identify_company,
    search_people,
    web_search,
)


class DossierError(Exception):
    """Raised when we cannot assemble a dossier for the requested company."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _first_or_none(xs: Any) -> Any:
    if isinstance(xs, list) and xs:
        return xs[0]
    return None


def _current_employment(person: dict[str, Any]) -> dict[str, Any]:
    current = (
        person.get("experience", {}).get("employment_details", {}).get("current")
    )
    if isinstance(current, list):
        return current[0] if current else {}
    if isinstance(current, dict):
        return current
    return {}


def _person_from_enrich(p: dict[str, Any]) -> PersonCard:
    """Convert a record from company_data.people.* into a PersonCard."""
    bp = p.get("basic_profile", {}) or {}
    pn = p.get("professional_network", {}) or {}
    social = p.get("social_handles", {}) or {}
    linkedin = (
        social.get("professional_network_identifier", {}).get("profile_url")
        or None
    )
    return PersonCard(
        name=bp.get("name") or pn.get("name") or "Unknown",
        title=bp.get("current_title") or pn.get("current_title"),
        headline=bp.get("headline") or pn.get("headline"),
        linkedin_url=linkedin,
        location=(bp.get("location") or {}).get("raw"),
    )


def _person_from_search(p: dict[str, Any]) -> PersonCard:
    """Convert a record from /person/search into a PersonCard."""
    bp = p.get("basic_profile", {}) or {}
    current = _current_employment(p)
    return PersonCard(
        name=bp.get("name") or "Unknown",
        title=current.get("title"),
        headline=bp.get("headline"),
        linkedin_url=p.get("professional_network_url"),
        location=(bp.get("location") or {}).get("raw"),
    )


def _dedupe_people(cards: list[PersonCard], cap: int) -> list[PersonCard]:
    seen: set[str] = set()
    out: list[PersonCard] = []
    for c in cards:
        key = (c.linkedin_url or c.name).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
        if len(out) >= cap:
            break
    return out


def _build_snapshot(cd: dict[str, Any]) -> CompanySnapshot:
    basic = cd.get("basic_info", {}) or {}
    headcount = cd.get("headcount", {}) or {}
    funding = cd.get("funding", {}) or {}
    hiring = cd.get("hiring", {}) or {}
    locations = cd.get("locations", {}) or {}
    competitors = cd.get("competitors", {}) or {}

    growth = headcount.get("growth_percent") or {}
    investors_raw = funding.get("investors") or []
    investor_names = [
        inv.get("name") for inv in investors_raw if isinstance(inv, dict) and inv.get("name")
    ]
    comp_websites = competitors.get("websites") or []

    hq_parts = [
        locations.get("hq_city"),
        locations.get("hq_state"),
        locations.get("hq_country"),
    ]
    hq = ", ".join([p for p in hq_parts if p]) or locations.get("headquarters")

    recent_titles = hiring.get("recent_titles_csv") or ""
    recent_titles_list = [t.strip() for t in recent_titles.split(",") if t.strip()]

    return CompanySnapshot(
        name=basic.get("name") or "",
        domain=basic.get("primary_domain"),
        website=basic.get("website"),
        description=basic.get("description"),
        year_founded=basic.get("year_founded"),
        company_type=basic.get("company_type"),
        employee_count_range=basic.get("employee_count_range"),
        headcount_total=headcount.get("total"),
        headcount_growth_percent=growth.get("yoy") or growth.get("six_months"),
        industries=basic.get("industries") or [],
        hq_location=hq,
        funding_total_usd=funding.get("total_investment_usd"),
        last_round_amount_usd=funding.get("last_round_amount_usd"),
        last_round_type=funding.get("last_round_type"),
        last_fundraise_date=funding.get("last_fundraise_date"),
        investors=investor_names,
        hiring_openings_count=hiring.get("openings_count"),
        hiring_recent_titles=recent_titles_list[:10],
        competitors=comp_websites[:10],
    )


def _build_signals(cd: dict[str, Any], web_results: list[dict[str, Any]]) -> list[Signal]:
    """Merge company news with live web search results, dedupe by URL."""
    signals: list[Signal] = []
    seen_urls: set[str] = set()

    for n in (cd.get("news") or [])[:5]:
        url = n.get("article_url")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        signals.append(
            Signal(
                headline=n.get("article_title") or "",
                url=url,
                published_at=str(n.get("article_publish_date")) if n.get("article_publish_date") else None,
            )
        )

    for w in web_results:
        url = w.get("url")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        signals.append(
            Signal(
                headline=w.get("title") or "",
                url=url,
                summary=w.get("snippet"),
            )
        )

    return [s for s in signals if s.headline][:8]


def _people_from_enrich_section(people_section: dict[str, Any]) -> list[PersonCard]:
    """Extract founders + decision_makers + cxos as PersonCards."""
    if not people_section:
        return []
    cards: list[PersonCard] = []
    for bucket in ("founders", "decision_makers", "cxos"):
        for p in (people_section.get(bucket) or []):
            try:
                cards.append(_person_from_enrich(p))
            except Exception:
                continue
    return cards


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


async def _resolve_company(name: str) -> tuple[str, str]:
    """Resolve a user-typed name to (resolved_name, primary_domain)."""
    try:
        resp = await identify_company(name)
    except CrustdataError as e:
        raise DossierError(f"Crustdata identify failed: {e.detail}") from e

    if not resp or not resp[0].get("matches"):
        raise DossierError(f"No company matches found for '{name}'.")

    best = resp[0]["matches"][0]["company_data"]
    basic = best.get("basic_info", {}) or {}
    domain = basic.get("primary_domain")
    resolved_name = basic.get("name") or name
    if not domain:
        raise DossierError(f"Company '{name}' matched but has no primary domain.")
    return resolved_name, domain


async def build_brief(company: str, role: str) -> RawDossier:
    """Assemble the raw dossier for Brief mode."""
    resolved_name, domain = await _resolve_company(company)

    enrich_task = asyncio.create_task(enrich_company(domain))
    web_task = asyncio.create_task(
        web_search(f"{resolved_name} {role}", limit=5)
    )
    enrich_resp, web_resp = await asyncio.gather(enrich_task, web_task)

    if not enrich_resp or not enrich_resp[0].get("matches"):
        raise DossierError(f"Could not enrich company at domain '{domain}'.")

    cd = enrich_resp[0]["matches"][0]["company_data"]
    snapshot = _build_snapshot(cd)
    people = _dedupe_people(
        _people_from_enrich_section(cd.get("people") or {}), cap=6
    )
    signals = _build_signals(cd, web_resp.get("results") or [])

    return RawDossier(
        company=snapshot,
        people=people,
        signals=signals,
    )


async def build_playbook(company: str, role: str) -> RawDossier:
    """
    Assemble a deeper dossier for Playbook mode.

    Adds a company-wide person search and a second web query focused on
    strategy/bet signals, so GPT-5 has material for the first-month and
    'the bet' sections.
    """
    resolved_name, domain = await _resolve_company(company)

    enrich_task = asyncio.create_task(enrich_company(domain))
    web_recent_task = asyncio.create_task(
        web_search(f"{resolved_name} {role}", limit=5)
    )
    web_strategy_task = asyncio.create_task(
        web_search(f"{resolved_name} strategy customers product launch", limit=5)
    )
    search_task = asyncio.create_task(
        search_people(resolved_name, limit=10)
    )

    enrich_resp, web_recent, web_strategy, search_resp = await asyncio.gather(
        enrich_task, web_recent_task, web_strategy_task, search_task,
        return_exceptions=True,
    )

    if isinstance(enrich_resp, Exception) or not enrich_resp or not enrich_resp[0].get("matches"):
        raise DossierError(f"Could not enrich company at domain '{domain}'.")

    cd = enrich_resp[0]["matches"][0]["company_data"]
    snapshot = _build_snapshot(cd)

    leadership = _people_from_enrich_section(cd.get("people") or {})
    search_people_cards: list[PersonCard] = []
    if isinstance(search_resp, dict):
        for p in (search_resp.get("profiles") or []):
            try:
                search_people_cards.append(_person_from_search(p))
            except Exception:
                continue
    people = _dedupe_people(leadership + search_people_cards, cap=14)

    web_results: list[dict[str, Any]] = []
    if isinstance(web_recent, dict):
        web_results.extend(web_recent.get("results") or [])
    if isinstance(web_strategy, dict):
        web_results.extend(web_strategy.get("results") or [])
    signals = _build_signals(cd, web_results)

    return RawDossier(
        company=snapshot,
        people=people,
        signals=signals,
    )
