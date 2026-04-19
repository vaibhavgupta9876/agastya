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
from datetime import datetime, timedelta
from typing import Any

from app.models.schemas import (
    CompanySnapshot,
    HeadcountTrend,
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
from app.services.prewarm import registry as prewarm_registry
from app.services.role import classify_role


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


# Title patterns that indicate the person is NOT an employee — investors,
# advisors, board members can leak into the enrich `decision_makers` bucket.
_NON_EMPLOYEE_TITLE_PATTERNS = (
    "investor",
    "advisor",
    "board member",
    "board observer",
    "limited partner",
    "general partner",
    "venture partner",
    "operating partner",
    "angel ",
    "early backer",
)


def _is_non_employee_title(title: str | None) -> bool:
    if not title:
        return False
    t = title.lower()
    return any(p in t for p in _NON_EMPLOYEE_TITLE_PATTERNS)


# Role family inference. Used to rank enrich people by role relevance.
_ROLE_FAMILIES: dict[str, tuple[str, ...]] = {
    "tech": (
        "engineer", "engineering", "developer", "swe", "sde", "mts",
        "member of technical staff", "research", "ml", "ai", "data scientist",
        "infrastructure", "infra", "platform", "backend", "frontend",
        "fullstack", "full stack", "ios", "android", "mobile", "devops",
        "sre", "security", "architect",
    ),
    "product": ("product manager", "product", " pm ", "product owner", "designer", "design", "ux", "ui"),
    "sales": ("sales", "account executive", "ae ", "bdr", "sdr", "gtm", "go-to-market", "revenue"),
    "marketing": ("marketing", "growth", "brand", "communications", "comms"),
    "ops": ("operations", "ops ", "supply chain", "logistics"),
    "finance": ("finance", "cfo", "controller", "accountant", "fp&a"),
    "people": ("hr ", "hrbp", "people ops", "talent", "recruit"),
    "legal": ("legal", "counsel", "compliance"),
}

_FAMILY_LEADERSHIP_HINTS: dict[str, tuple[str, ...]] = {
    "tech": ("cto", "chief technology", "vp eng", "vp of engineering",
             "head of engineering", "head of research", "chief scientist",
             "research lead", "vp research", "principal", "staff", "distinguished"),
    "product": ("cpo", "chief product", "vp product", "head of product", "vp design", "head of design"),
    "sales": ("cro", "chief revenue", "vp sales", "head of sales", "vp of sales"),
    "marketing": ("cmo", "chief marketing", "vp marketing", "head of marketing"),
    "ops": ("coo", "chief operating", "vp operations", "head of operations"),
    "finance": ("cfo", "chief financial", "vp finance", "head of finance"),
    "people": ("chro", "chief people", "vp people", "head of people"),
    "legal": ("general counsel", "chief legal"),
}


def _role_family(role: str | None) -> str:
    if not role:
        return "general"
    r = " " + role.lower() + " "
    for fam, needles in _ROLE_FAMILIES.items():
        if any(n in r for n in needles):
            return fam
    return "general"


def _role_relevance_score(title: str | None, family: str) -> int:
    """Higher = more relevant to the role family. Range roughly -50..+50."""
    if not title:
        return 0
    t = title.lower()
    score = 0
    if family != "general":
        if any(n in t for n in _ROLE_FAMILIES.get(family, ())):
            score += 20
        if any(h in t for h in _FAMILY_LEADERSHIP_HINTS.get(family, ())):
            score += 25
        # Cross-family penalty so a Marketing VP doesn't beat a senior eng.
        for other_fam, needles in _ROLE_FAMILIES.items():
            if other_fam == family or other_fam == "general":
                continue
            if any(n in t for n in needles):
                score -= 15
                break
    # Always boost C-suite / co-founders modestly — they're useful context.
    if any(h in t for h in ("ceo", "co-founder", "cofounder", "founder", "president")):
        score += 8
    return score


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

    # Drop "→ unknown" departures — without a destination this looks like noise
    # in the UI ("name went to None"). The current employer is what gives the
    # row narrative weight; without it, skip.
    if not (_company_name(cur) or "").strip():
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


def _build_headcount_trends(cd: dict[str, Any]) -> list[HeadcountTrend]:
    """
    Compose a per-function view of the company: current share + growth rate.

    Inputs (all from /company/enrich):
      - headcount.by_function_timeseries.CURRENT_FUNCTION — monthly counts per function
      - headcount.by_role_percent — current composition snapshot (0-100 pct)
      - hiring.by_function_qoq_pct — hiring velocity QoQ (ratio, -1..+inf)

    YoY growth is computed from the timeseries (latest vs 12mo prior).
    Output is capped, sorted by growth magnitude, and trimmed of noise functions.
    """
    headcount = cd.get("headcount") or {}
    hiring = cd.get("hiring") or {}

    series_by_fn = (headcount.get("by_function_timeseries") or {}).get("CURRENT_FUNCTION") or {}
    share_by_fn = headcount.get("by_role_percent") or {}
    hiring_qoq = hiring.get("by_function_qoq_pct") or {}

    if not series_by_fn:
        return []

    trends: list[HeadcountTrend] = []
    for fn, series in series_by_fn.items():
        if not isinstance(series, list) or not series:
            continue
        parsed: list[tuple[datetime, int]] = []
        for entry in series:
            if not isinstance(entry, dict):
                continue
            d_str = (entry.get("date") or "")[:10]
            c = entry.get("employee_count")
            if not d_str or c is None:
                continue
            try:
                parsed.append((datetime.fromisoformat(d_str), int(c)))
            except (ValueError, TypeError):
                continue
        if not parsed:
            continue
        parsed.sort(key=lambda t: t[0])
        latest_date, latest_count = parsed[-1]

        # Find the most recent entry on or before (latest - 12 months).
        target_date = latest_date - timedelta(days=365)
        older = [p for p in parsed if p[0] <= target_date]
        yoy_pct: float | None = None
        if older:
            _, old_count = older[-1]
            if old_count > 0:
                yoy_pct = (latest_count - old_count) / old_count * 100.0

        raw_hiring = hiring_qoq.get(fn)
        hiring_qoq_pct = (
            float(raw_hiring) * 100.0 if isinstance(raw_hiring, (int, float)) else None
        )

        raw_share = share_by_fn.get(fn)
        share_pct = float(raw_share) if isinstance(raw_share, (int, float)) else None

        trends.append(
            HeadcountTrend(
                function=fn,
                share_pct=share_pct,
                current_count=latest_count,
                yoy_pct=yoy_pct,
                hiring_qoq_pct=hiring_qoq_pct,
            )
        )

    # Drop tiny functions — a 6× jump from 2 to 15 people is noise, not a bet.
    # Floor: 2% of company OR at least 20 people absolute.
    trends = [
        t for t in trends
        if (t.share_pct or 0) >= 2.0 or (t.current_count or 0) >= 20
    ]

    # Mix "pillars" (top by share — where the company actually lives) with
    # "bets" (top by growth — where it's leaning). Pure growth-sort is too
    # easily dominated by small-base noise.
    by_share = sorted(trends, key=lambda t: -(t.share_pct or 0.0))
    by_growth = sorted(
        [t for t in trends if t.yoy_pct is not None],
        key=lambda t: -(t.yoy_pct or 0.0),
    )

    picked: list[HeadcountTrend] = []
    seen: set[str] = set()

    # Two pillars: biggest functions by share.
    for t in by_share[:2]:
        if t.function not in seen:
            picked.append(t)
            seen.add(t.function)

    # Three bets: fastest growing (excluding already picked).
    grown = 0
    for t in by_growth:
        if grown >= 3 or len(picked) >= 5:
            break
        if t.function in seen:
            continue
        picked.append(t)
        seen.add(t.function)
        grown += 1

    # Backfill if growth list was short.
    for t in by_share[2:]:
        if len(picked) >= 5:
            break
        if t.function not in seen:
            picked.append(t)
            seen.add(t.function)

    # Final order: by share desc, so the "where they live" row reads first.
    picked.sort(key=lambda t: -(t.share_pct or 0.0))
    return picked


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


def _people_from_enrich_section(
    people_section: dict[str, Any], role: str | None = None
) -> list[PersonCard]:
    """
    Extract founders + decision_makers + cxos as PersonCards, filtered for
    actual employees (drops investors/advisors/board) and ranked by relevance
    to the candidate's target role.
    """
    if not people_section:
        return []
    family = _role_family(role)
    cards: list[tuple[int, PersonCard]] = []
    for bucket in ("founders", "decision_makers", "cxos"):
        for p in (people_section.get(bucket) or []):
            try:
                card = _person_from_enrich(p)
            except Exception:
                continue
            if _is_non_employee_title(card.title):
                continue
            score = _role_relevance_score(card.title, family)
            cards.append((score, card))
    cards.sort(key=lambda sc: -sc[0])
    return [c for _, c in cards]


def _role_matched_hires(hires: Movement, role: str) -> list[PersonCard]:
    """Surface senior recent hires whose title matches the role family."""
    family = _role_family(role)
    if family == "general":
        return []
    matched: list[tuple[int, PersonCard]] = []
    for p in hires.people:
        score = _role_relevance_score(p.title, family)
        if score < 20:
            continue
        # Boost by inferred title seniority (lower _seniority_from_title = better).
        rank_bonus = max(0, 10 - _seniority_from_title(p.title))
        matched.append(
            (
                score + rank_bonus,
                PersonCard(
                    name=p.name,
                    title=p.title,
                    headline=p.headline,
                    linkedin_url=p.linkedin_url,
                    location=None,
                ),
            )
        )
    matched.sort(key=lambda sc: -sc[0])
    return [c for _, c in matched]


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


async def _resolve_company(name: str, domain: str | None = None) -> tuple[str, str]:
    """
    Resolve a user-typed name to (resolved_name, primary_domain).

    When the caller has already disambiguated via /identify, passing `domain`
    skips the identify round-trip. `name` is then treated as the display name.
    """
    if domain:
        return name, domain

    try:
        resp = await identify_company(name)
    except CrustdataError as e:
        raise DossierError(f"Crustdata identify failed: {e.detail}") from e

    if not resp or not resp[0].get("matches"):
        raise DossierError(f"No company matches found for '{name}'.")

    best = resp[0]["matches"][0]["company_data"]
    basic = best.get("basic_info", {}) or {}
    resolved_domain = basic.get("primary_domain")
    resolved_name = basic.get("name") or name
    if not resolved_domain:
        raise DossierError(f"Company '{name}' matched but has no primary domain.")
    return resolved_name, resolved_domain


def _customer_floor_tasks(resolved_name: str, domain: str) -> list[asyncio.Task]:
    """
    Beyond the generic "customer case study" query, mine the company's own
    site and logo-wall language — the richest sources for named customers.
    """
    return [
        asyncio.create_task(web_search(f"{resolved_name} customer case study", limit=5)),
        asyncio.create_task(web_search(f"site:{domain} customers", limit=5)),
        asyncio.create_task(web_search(f"site:{domain} case studies", limit=5)),
        asyncio.create_task(web_search(f'"{resolved_name}" powers OR trusts OR chose', limit=5)),
    ]


def _insider_tasks(resolved_name: str) -> list[asyncio.Task]:
    """
    Employee-voice and founder-voice material. Routed separately in synth so
    Glassdoor/Blind evidence feeds culture_warning and interview transcripts
    feed the_bet / how_they_talk.
    """
    return [
        asyncio.create_task(web_search(f'site:glassdoor.com "{resolved_name}"', limit=5)),
        asyncio.create_task(web_search(f'site:teamblind.com "{resolved_name}"', limit=5)),
        asyncio.create_task(web_search(f'"{resolved_name} CEO" interview OR podcast', limit=5)),
    ]


def _flatten_web_results(responses: list[Any]) -> list[dict[str, Any]]:
    """Collect .results from a list of web_search responses, ignoring failures."""
    out: list[dict[str, Any]] = []
    for r in responses:
        if isinstance(r, dict):
            out.extend(r.get("results") or [])
    return out


def _insider_signals(raw_results: list[dict[str, Any]]) -> list[Signal]:
    """Normalize insider web_search results into Signals (dedup by URL)."""
    signals: list[Signal] = []
    seen: set[str] = set()
    for w in raw_results:
        url = w.get("url")
        if not w.get("title") and not w.get("snippet"):
            continue
        if url and url in seen:
            continue
        if url:
            seen.add(url)
        signals.append(
            Signal(
                headline=w.get("title") or "",
                url=url,
                summary=w.get("snippet"),
            )
        )
    return [s for s in signals if s.headline][:12]


async def build_brief(company: str, role: str, domain: str | None = None) -> RawDossier:
    """Assemble the raw dossier for Brief mode."""
    resolved_name, domain = await _resolve_company(company, domain)

    # Role-independent work: hits prewarm cache if the frontend already fired.
    prewarm_task = asyncio.create_task(prewarm_registry.get_or_fetch(resolved_name, domain))
    # Role-specific work runs in parallel with the prewarm wait.
    web_task = asyncio.create_task(web_search(f"{resolved_name} {role}", limit=5))
    role_departures_task = asyncio.create_task(recent_departures(resolved_name, [role], limit=10))
    classify_task = asyncio.create_task(classify_role(role))

    prewarm, web_resp, role_departures_resp, classify_resp = await asyncio.gather(
        prewarm_task, web_task, role_departures_task, classify_task,
        return_exceptions=True,
    )
    if isinstance(prewarm, Exception):
        raise DossierError(f"Prewarm failed: {prewarm}") from prewarm
    role_classification = classify_resp if not isinstance(classify_resp, Exception) else None

    enrich_resp = prewarm.enrich_resp
    if not enrich_resp or not enrich_resp[0].get("matches"):
        raise DossierError(f"Could not enrich company at domain '{domain}'.")

    cd = enrich_resp[0]["matches"][0]["company_data"]
    snapshot = _build_snapshot(cd)
    web_results: list[dict[str, Any]] = []
    if isinstance(web_resp, dict):
        web_results.extend(web_resp.get("results") or [])
    web_results.extend(prewarm.customer_results)
    signals = _build_signals(cd, web_results)
    insider_snippets = _insider_signals(prewarm.insider_results)

    hires = _build_movement(prewarm.hires_resp, snapshot.name or resolved_name, "hire")
    departures = _build_movement(prewarm.departures_resp, snapshot.name or resolved_name, "departure")

    leadership = _people_from_enrich_section(cd.get("people") or {}, role=role)
    role_hires = _role_matched_hires(hires, role)
    # Wider candidate pool — synth picks and ranks interviewer-loop matches.
    interleaved = leadership[:4] + role_hires[:6] + leadership[4:]
    people = _dedupe_people(interleaved, cap=12)

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
        insider_snippets=insider_snippets,
        hires=hires,
        departures=departures,
        alumni_in_role=_dedupe_people(alumni_cards, cap=3),
        role=role_classification,
        headcount_trends=_build_headcount_trends(cd),
    )


async def build_playbook(company: str, role: str, domain: str | None = None) -> RawDossier:
    """
    Assemble a deeper dossier for Playbook mode.

    Adds a company-wide person search and a second web query focused on
    strategy/bet signals, so GPT-5 has material for the first-month and
    'the bet' sections.
    """
    resolved_name, domain = await _resolve_company(company, domain)

    prewarm_task = asyncio.create_task(prewarm_registry.get_or_fetch(resolved_name, domain))
    web_recent_task = asyncio.create_task(web_search(f"{resolved_name} {role}", limit=5))
    classify_task = asyncio.create_task(classify_role(role))

    prewarm, web_recent, classify_resp = await asyncio.gather(
        prewarm_task, web_recent_task, classify_task,
        return_exceptions=True,
    )
    if isinstance(prewarm, Exception):
        raise DossierError(f"Prewarm failed: {prewarm}") from prewarm
    role_classification = classify_resp if not isinstance(classify_resp, Exception) else None

    enrich_resp = prewarm.enrich_resp
    if not enrich_resp or not enrich_resp[0].get("matches"):
        raise DossierError(f"Could not enrich company at domain '{domain}'.")

    cd = enrich_resp[0]["matches"][0]["company_data"]
    snapshot = _build_snapshot(cd)

    hires = _build_movement(prewarm.hires_resp, snapshot.name or resolved_name, "hire")
    departures = _build_movement(prewarm.departures_resp, snapshot.name or resolved_name, "departure")

    leadership = _people_from_enrich_section(cd.get("people") or {}, role=role)
    role_hires = _role_matched_hires(hires, role)
    search_people_cards: list[PersonCard] = []
    if isinstance(prewarm.search_resp, dict):
        for p in (prewarm.search_resp.get("profiles") or []):
            try:
                search_people_cards.append(_person_from_search(p))
            except Exception:
                continue
    # Wider candidate pool — synth picks and ranks interviewer-loop matches.
    interleaved = leadership[:4] + role_hires[:6] + leadership[4:] + search_people_cards
    people = _dedupe_people(interleaved, cap=24)

    web_results: list[dict[str, Any]] = []
    if isinstance(web_recent, dict):
        web_results.extend(web_recent.get("results") or [])
    web_results.extend(prewarm.strategy_web_results)
    web_results.extend(prewarm.customer_results)
    signals = _build_signals(cd, web_results)
    insider_snippets = _insider_signals(prewarm.insider_results)

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
        insider_snippets=insider_snippets,
        hires=hires,
        departures=departures,
        veterans=veterans,
        role=role_classification,
        headcount_trends=_build_headcount_trends(cd),
    )
