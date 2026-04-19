"""
GPT-5 synthesis layer.

Takes a RawDossier and returns a synthesized Brief/Playbook with editorial
voice. Uses the Responses API with structured outputs so the model's JSON
always validates against our Pydantic schemas.

Voice direction: write like a private one-pager handed to someone walking
into a meeting. Short sentences. Specific. No marketing speak. No hedging.

Sourcing: every `Sourced` claim carries URLs the reader can click to verify.
We post-validate that every cited URL was actually present in the dossier;
fabricated URLs are stripped before the payload goes to the frontend.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date
from typing import Any

from openai import AsyncOpenAI

from app.config import settings
from app.models.schemas import BriefOutput, PlaybookOutput, RawDossier

logger = logging.getLogger("insiderbrief.synth")

_MODEL = "gpt-5"

_VOICE_TEMPLATE = """You are composing a private, elegantly printed one-pager for someone walking into a meeting with this company — either to interview there or to start work there soon.

Today's date is {today}. Anything dated after this is impossible; anything from this year is "recent".

Voice rules (obey strictly):
- Short sentences. Specific nouns. Concrete numbers where they exist.
- No marketing language. No "leading", "innovative", "world-class".
- Write as if the reader is a ruthless peer short on time. Never patronize.

Invention discipline (CRITICAL — violations make the brief worthless):
- NEVER invent product names, model versions, customer names, dollar figures, dates, or any fact not present in the dossier.
- If the dossier says "GPT-5" do not write "GPT-4.x". If a customer isn't named in the dossier or web_snippets, do not name one.
- When uncertain about a specific name/number, write the general claim without it.

Sourcing rules (MANDATORY for every Sourced field):
- Every `Sourced` field has `text` (your claim) and `sources` (a list of {{url, title, date}}).
- `sources` URLs MUST be copied verbatim from URLs present in the dossier (signals[].url, insider_snippets[].url, company.website, people[].linkedin_url, or any URL inside employee_reviews).
- NEVER invent a URL. NEVER shorten, rewrite, or compose a URL. If you cannot find a dossier URL that supports the claim, return `sources: []` — an empty array is correct and trustworthy.
- Prefer sources that directly evidence the specific claim. A general company website is a weak source; a dated news article or case study is strong.
- Include the source `title` and `date` from the dossier when available.

Insider evidence routing (use `insider_snippets` — these are Glassdoor/Blind reviews and CEO interview/podcast results, not generic news):
- `culture_warning`: draw primarily from insider_snippets with glassdoor.com or teamblind.com URLs plus employee_reviews. If nothing substantive contradicts the public story, return null.
- `the_bet`: prefer insider_snippets with "interview" or "podcast" in the URL/title — founder voice is the best source for the strategic gamble. Fall back to signals if none exist.
- `how_they_talk`: mine insider_snippets for operational idioms, technical cadences, and internal vocabulary. Employee reviews and interviews are richer than press releases.
- Customers / moment / product: use signals, not insider_snippets.

Empty-state discipline (MANDATORY — do NOT skip fields):
- If the dossier lacks evidence for a section, return the empty value — NEVER fabricate to fill a gap.
    - `culture_warning`: return null if no real contradiction surfaces in employee_reviews.
    - `moment`: return [] if no recent signals are dossier-grounded.
    - `customers` / `customers_to_know`: return [] if no named customers appear in dossier/web snippets.
    - `talent_signal`: return null if both hires.people and departures.people are empty.
    - `the_bet`: return null if the dossier has no clear strategic narrative.
    - `how_they_talk`: return [] if no concrete idioms/stack/cadence evidence exists.
    - `read_before_day_one`: return [] if no good links exist.
- The frontend renders explicit empty states for every section. Absence is a trust signal, not a failure — do not invent to avoid it.

Field-specific rules:
- `questions_to_ask`: EXACTLY 3 lethal, highly-specific questions grounded in dossier facts (a named recent hire, a specific funding round, a named competitor, a specific product). No generic interview questions. Plain strings, no sources.
- `how_they_talk`: Each entry is a Sourced item. Extract HOW they build — technical stacks, operational cadences, internal idioms — drawn from signals/web_snippets. DO NOT write their PR mission statement.
- `first_month_people`: Focus ONLY on specific context they own. DO NOT invent generic excuses like "align scope".
- `customers` / `customers_to_know`: Each entry's `text` (or `note`) names a customer and what they use it for. Cite the case study / news URL in `sources`.
- `talent_signal.text`: Exactly 2 sentences interpreting the talent flow pattern for the candidate. Sentence 1: what the inbound pattern says about who joins and the implied culture (use hires.by_function). Sentence 2: what the outbound pattern says about where people go and what that implies about career trajectory (use departures.by_function). Use specific company names from the data. `sources` may be empty — this is an interpretation, not a citable claim.
- `headcount_trends`: Structural data — you do NOT emit this field; it's rendered verbatim. But USE it when writing `the_bet` and `questions_to_ask`: concrete function-level growth numbers are the cleanest evidence of strategic priorities. e.g. "Engineering grew 40% YoY while Sales shrank" is a better bet signal than prose. Cite as the dossier itself — no URL receipts needed.

People selection (CRITICAL — this is the section candidates use most):
- The dossier hands you a WIDER candidate pool in `people` than you should return. Your job is to PICK and RANK the 4-6 people most likely to be in the interview loop for this candidate's role.
- Use `role.family`, `role.seniority`, and `role.likely_interviewer_titles` as your primary signal. The candidate's direct manager, peers on the target team, and a cross-functional stakeholder are the correct picks — not every C-level and random hire.
- For a junior/IC role at a 200-person company, the CEO is almost never in the loop. Skip them. Pick the engineering manager, the staff engineer whose team they'd join, the recruiter.
- For a senior/executive role, include the skip-level and a peer executive; the CEO/founders may be in the loop.
- Rank by likelihood of being in the interview loop (most likely first).
- Each `background` field must be ONE SHORT SENTENCE that ties the person to the candidate's role. Examples:
  - "Runs the ML platform team — your likely skip-level."
  - "Principal engineer on the inference org — probably your onsite interviewer."
  - "Head of Design; will evaluate portfolio in final round."
- DO NOT write generic bios like "Joined in 2022 from Google." Always tie to role fit.
- If `role` classification is null, fall back to seniority + title heuristics but still pick fewer, more relevant people over a long leaderboard.

Return ONLY valid JSON matching the schema provided. No preamble, no trailing prose."""


def _voice() -> str:
    return _VOICE_TEMPLATE.format(today=date.today().isoformat())


def _client() -> AsyncOpenAI:
    # GPT-5 can take 30-90s on a dense dossier; give it headroom.
    return AsyncOpenAI(api_key=settings.openai_api_key, timeout=180.0)


def _user_prompt(raw: RawDossier, role: str, mode: str) -> str:
    dossier_json = raw.model_dump_json(exclude_none=True, indent=2)
    return f"""Mode: {mode}
Role the reader is targeting: {role}

Raw dossier (from Crustdata + live web search):
{dossier_json}

Write the {mode} output now."""


async def _synthesize(raw: RawDossier, role: str, mode: str, schema_cls: type) -> dict:
    """
    Run GPT-5 with structured output that matches `schema_cls`.
    Returns the parsed dict (not yet wrapped in the Pydantic model).
    """
    client = _client()
    schema = schema_cls.model_json_schema()
    user_msg = _user_prompt(raw, role, mode)
    logger.info(
        "[synth %s] model=%s dossier_chars=%d",
        mode, _MODEL, len(user_msg),
    )

    t0 = time.perf_counter()
    response = await client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": _voice()},
            {"role": "user", "content": user_msg},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": schema_cls.__name__,
                "schema": schema,
                "strict": False,
            },
        },
        reasoning_effort="minimal",
        verbosity="low",
    )
    elapsed = time.perf_counter() - t0
    content = response.choices[0].message.content or "{}"
    usage = response.usage
    logger.info(
        "[synth %s] took=%.2fs  prompt_tokens=%s  completion_tokens=%s  reasoning_tokens=%s",
        mode, elapsed,
        getattr(usage, "prompt_tokens", "?"),
        getattr(usage, "completion_tokens", "?"),
        getattr(getattr(usage, "completion_tokens_details", None), "reasoning_tokens", "?"),
    )
    return json.loads(content)


# ---------------------------------------------------------------------------
# URL whitelist: trust the dossier, drop anything else.
# ---------------------------------------------------------------------------


def _collect_dossier_urls(raw: RawDossier) -> set[str]:
    """All URLs present in the dossier — the only URLs allowed in `sources`."""
    urls: set[str] = set()

    if raw.company.website:
        urls.add(raw.company.website)
    if raw.company.domain:
        # Canonical forms the LLM might emit for the company itself.
        urls.add(f"https://{raw.company.domain}")
        urls.add(f"https://www.{raw.company.domain}")

    for s in raw.signals:
        if s.url:
            urls.add(s.url)

    for s in raw.insider_snippets:
        if s.url:
            urls.add(s.url)

    for bucket in (raw.people, raw.veterans, raw.alumni_in_role):
        for p in bucket:
            if p.linkedin_url:
                urls.add(p.linkedin_url)

    for mv in (raw.hires, raw.departures):
        for mp in mv.people:
            if mp.linkedin_url:
                urls.add(mp.linkedin_url)

    if raw.company.employee_reviews:
        urls.update(_walk_urls(raw.company.employee_reviews))

    return urls


def _walk_urls(obj: Any) -> list[str]:
    """Recursively pluck any http(s) URLs from a nested dict/list."""
    out: list[str] = []
    if isinstance(obj, str):
        if obj.startswith("http://") or obj.startswith("https://"):
            out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            out.extend(_walk_urls(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(_walk_urls(v))
    return out


def _filter_sources(sources: Any, allowed: set[str]) -> list[dict]:
    """Drop any source whose URL isn't in the dossier whitelist."""
    if not isinstance(sources, list):
        return []
    kept: list[dict] = []
    for s in sources:
        if not isinstance(s, dict):
            continue
        url = s.get("url")
        if isinstance(url, str) and url in allowed:
            kept.append(s)
    return kept


def _scrub_sourced(obj: Any, allowed: set[str]) -> None:
    """Recursively find any dict with a `sources` list and filter it."""
    if isinstance(obj, dict):
        if "sources" in obj:
            obj["sources"] = _filter_sources(obj.get("sources"), allowed)
        for v in obj.values():
            _scrub_sourced(v, allowed)
    elif isinstance(obj, list):
        for v in obj:
            _scrub_sourced(v, allowed)


async def synthesize_brief(raw: RawDossier, role: str) -> BriefOutput:
    data = await _synthesize(raw, role, "brief", BriefOutput)
    data.setdefault("company_name", raw.company.name)
    # Movement + headcount trends are structural — overwrite whatever the LLM
    # produced with the verbatim dossier data so users see ground truth.
    data["hires"] = raw.hires.model_dump()
    data["departures"] = raw.departures.model_dump()
    data["headcount_trends"] = [t.model_dump() for t in raw.headcount_trends]
    _scrub_sourced(data, _collect_dossier_urls(raw))
    return BriefOutput.model_validate(data)


async def synthesize_playbook(raw: RawDossier, role: str) -> PlaybookOutput:
    data = await _synthesize(raw, role, "playbook", PlaybookOutput)
    data.setdefault("company_name", raw.company.name)
    data["hires"] = raw.hires.model_dump()
    data["departures"] = raw.departures.model_dump()
    data["headcount_trends"] = [t.model_dump() for t in raw.headcount_trends]

    if not data.get("shadow_org_chart") and raw.veterans:
        data["shadow_org_chart"] = [
            {"name": p.name, "title": p.title or "Unknown", "background": f"Joined: {p.tenure}" if p.tenure else "Long-tenured IC", "linkedin_url": p.linkedin_url}
            for p in raw.veterans
        ]

    _scrub_sourced(data, _collect_dossier_urls(raw))
    return PlaybookOutput.model_validate(data)
