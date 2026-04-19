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

from app.models.schemas import (
    CompanySnapshot,
    Movement,
    MovementGroup,
    MovementPerson,
    PersonCard,
    RawDossier,
    Signal,
)
from app.services.crustdata import (
    CrustdataError,
    enrich_company,
    identify_company,
    recent_departures,
    recent_hires,
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
        tenure=current.get("start_date"),
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
        employee_reviews=cd.get("employee_reviews"),
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


# Title-keyword heuristic for ranking. Crustdata exposes seniority_level as a
# filterable field but does NOT return it in the response payload, so we infer
# from the title to pick which faces to surface first.
_TITLE_RANK = [
    (("ceo", "founder", "co-founder", "cofounder"), 0),
    (("president", "chief"), 1),
    (("evp", "svp"), 2),
    (("vp ", "vice president", "head of"), 3),
    (("director",), 4),
    (("principal", "staff", "lead"), 5),
    (("manager", "mgr"), 6),
    (("senior", "sr."), 7),
    (("intern",), 99),
]


def _seniority_from_title(title: str | None) -> int:
    if not title:
        return 50
    t = title.lower()
    for needles, rank in _TITLE_RANK:
        if any(n in t for n in needles):
            return rank
    return 20  # plain "Engineer", "PM", "Designer" — meaningful but mid


def _company_name(entry: dict[str, Any] | None) -> str | None:
    """Crustdata returns the company on past/current entries as `name`."""
    if not isinstance(entry, dict):
        return None
    return entry.get("name") or entry.get("company_name")


def _past_match(emp: dict[str, Any], target: str) -> dict[str, Any] | None:
    past = emp.get("past")
    if isinstance(past, dict):
        past = [past]
    if not isinstance(past, list):
        return None
    target_lower = target.lower()
    for entry in past:
        if isinstance(entry, dict) and (_company_name(entry) or "").lower() == target_lower:
            return entry
    return None


def _most_recent_past(emp: dict[str, Any], exclude: str) -> dict[str, Any] | None:
    past = emp.get("past")
    if isinstance(past, dict):
        past = [past]
    if not isinstance(past, list):
        return None
    candidates = [
        e for e in past
        if isinstance(e, dict) and (_company_name(e) or "").lower() != exclude.lower()
    ]
    candidates.sort(key=lambda e: e.get("end_date") or "", reverse=True)
    return candidates[0] if candidates else None


def _employment_details(p: dict[str, Any]) -> dict[str, Any]:
    emp = (p.get("experience") or {}).get("employment_details") or {}
    if isinstance(emp, list):
        emp = emp[0] if emp else {}
    return emp if isinstance(emp, dict) else {}


def _current(emp: dict[str, Any]) -> dict[str, Any]:
    cur = emp.get("current")
    if isinstance(cur, list):
        return cur[0] if cur else {}
    return cur if isinstance(cur, dict) else {}


def _linkedin_url(p: dict[str, Any]) -> str | None:
    direct = p.get("professional_network_url")
    if direct:
        return direct
    return (
        ((p.get("social_handles") or {}).get("professional_network_identifier") or {})
        .get("profile_url")
    )


def _movement_person_from_hire(p: dict[str, Any], target: str) -> MovementPerson | None:
    bp = p.get("basic_profile") or {}
    emp = _employment_details(p)
    cur = _current(emp)
    if (_company_name(cur) or "").lower() != target.lower():
        return None
    prev = _most_recent_past(emp, exclude=target)
    return MovementPerson(
        name=bp.get("name") or "Unknown",
        title=cur.get("title"),
        headline=(bp.get("headline") if bp.get("headline") not in (None, "-") else None),
        linkedin_url=_linkedin_url(p),
        seniority_level=None,
        event_date=cur.get("start_date"),
        counterparty_company=_company_name(prev),
        counterparty_title=(prev or {}).get("title"),
    )


def _movement_person_from_departure(p: dict[str, Any], target: str) -> MovementPerson | None:
    """
    Two filters Crustdata can't do server-side:
      1. Drop internal title changes — `recently_changed_jobs` flags any role
         change, including a promotion within target. Skip if current employer
         is still target.
      2. Drop stale departures — the flag captures any recent profile change,
         not specifically a recent departure from target. Require the most
         recent target-tenure to have ended within ~18 months.
    """
    bp = p.get("basic_profile") or {}
    emp = _employment_details(p)
    cur = _current(emp)

    if (_company_name(cur) or "").lower() == target.lower():
        return None

    past_list = emp.get("past")
    if isinstance(past_list, dict):
        past_list = [past_list]
    if not isinstance(past_list, list):
        return None
    target_tenures = [
        e for e in past_list
        if isinstance(e, dict) and (_company_name(e) or "").lower() == target.lower()
    ]
    if not target_tenures:
        return None
    target_past = max(target_tenures, key=lambda e: e.get("end_date") or "")

    end_date_str = (target_past.get("end_date") or "")[:10]
    if end_date_str:
        try:
            from datetime import date
            end_d = date.fromisoformat(end_date_str)
            if (date.today() - end_d).days > 540:
                return None
        except ValueError:
            pass

    return MovementPerson(
        name=bp.get("name") or "Unknown",
        title=target_past.get("title"),
        headline=(bp.get("headline") if bp.get("headline") not in (None, "-") else None),
        linkedin_url=_linkedin_url(p),
        seniority_level=None,
        event_date=target_past.get("end_date"),
        counterparty_company=_company_name(cur),
        counterparty_title=cur.get("title"),
    )


def _group_by_counterparty(
    people: list[MovementPerson], top: int = 5
) -> list[MovementGroup]:
    """
    Group by counterparty company — for hires this is "where they came from",
    for departures it's "where they went". More signal than function bucketing.
    """
    counts: dict[str, int] = {}
    for p in people:
        key = (p.counterparty_company or "Other / unknown").strip()
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    return [MovementGroup(function=fn, count=ct) for fn, ct in ranked[:top]]


def _build_movement(
    raw_resp: Any,
    target: str,
    direction: str,  # "hire" | "departure"
    cap: int = 12,
) -> Movement:
    if not isinstance(raw_resp, dict):
        return Movement()
    profiles = raw_resp.get("profiles") or []
    total = raw_resp.get("total_count") or len(profiles)
    converter = (
        _movement_person_from_hire if direction == "hire" else _movement_person_from_departure
    )
    people: list[MovementPerson] = []
    seen: set[str] = set()
    for p in profiles:
        try:
            mp = converter(p, target)
        except Exception:
            continue
        if not mp:
            continue
        key = (mp.linkedin_url or mp.name).lower()
        if key in seen:
            continue
        seen.add(key)
        people.append(mp)
    people.sort(key=lambda mp: _seniority_from_title(mp.title))
    capped = people[:cap]
    return Movement(
        total=int(total) if total else len(people),
        people=capped,
        by_function=_group_by_counterparty(capped),
    )


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
    hires_task = asyncio.create_task(recent_hires(resolved_name, days=365, limit=25))
    departures_task = asyncio.create_task(recent_departures(resolved_name, limit=50))
    role_departures_task = asyncio.create_task(recent_departures(resolved_name, [role], limit=10))

    enrich_resp, web_resp, hires_resp, departures_resp, role_departures_resp = await asyncio.gather(
        enrich_task, web_task, hires_task, departures_task, role_departures_task,
        return_exceptions=True,
    )

    if isinstance(enrich_resp, Exception) or not enrich_resp or not enrich_resp[0].get("matches"):
        raise DossierError(f"Could not enrich company at domain '{domain}'.")

    cd = enrich_resp[0]["matches"][0]["company_data"]
    snapshot = _build_snapshot(cd)
    people = _dedupe_people(
        _people_from_enrich_section(cd.get("people") or {}), cap=6
    )
    web_results = web_resp.get("results") if isinstance(web_resp, dict) else []
    signals = _build_signals(cd, web_results or [])

    hires = _build_movement(hires_resp, snapshot.name or resolved_name, "hire")
    departures = _build_movement(departures_resp, snapshot.name or resolved_name, "departure")

    alumni_cards: list[PersonCard] = []
    if isinstance(role_departures_resp, dict):
        for p in (role_departures_resp.get("profiles") or []):
            try:
                alumni_cards.append(_person_from_search(p))
            except Exception:
                continue

    return RawDossier(
        company=snapshot,
        people=people,
        signals=signals,
        hires=hires,
        departures=departures,
        alumni_in_role=_dedupe_people(alumni_cards, cap=3)
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
        search_people(resolved_name, limit=30)
    )
    hires_task = asyncio.create_task(recent_hires(resolved_name, days=365, limit=25))
    departures_task = asyncio.create_task(recent_departures(resolved_name, limit=50))

    enrich_resp, web_recent, web_strategy, search_resp, hires_resp, departures_resp = await asyncio.gather(
        enrich_task, web_recent_task, web_strategy_task, search_task, hires_task, departures_task,
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

    hires = _build_movement(hires_resp, snapshot.name or resolved_name, "hire")
    departures = _build_movement(departures_resp, snapshot.name or resolved_name, "departure")

    # Shadow Org Chart: ICs with longest tenure
    veterans: list[PersonCard] = []
    cxo_words = {"chief", "vp", "president", "founder", "head", "director"}
    valid_tenure_cards = [
        c for c in search_people_cards 
        if c.tenure and c.title and not any(w in c.title.lower() for w in cxo_words)
    ]
    valid_tenure_cards.sort(key=lambda c: c.tenure or "9999-99-99")
    veterans = _dedupe_people(valid_tenure_cards, cap=4)

    return RawDossier(
        company=snapshot,
        people=people,
        signals=signals,
        hires=hires,
        departures=departures,
        veterans=veterans,
    )
