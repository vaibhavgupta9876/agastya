"""
GPT-5 synthesis layer.

Takes a RawDossier and returns a synthesized Brief/Playbook with editorial
voice. Uses the Responses API with structured outputs so the model's JSON
always validates against our Pydantic schemas.

Voice direction: write like a private one-pager handed to someone walking
into a meeting. Short sentences. Specific. No marketing speak. No hedging.
"""

from __future__ import annotations

import json
from datetime import date

from openai import AsyncOpenAI

from app.config import settings
from app.models.schemas import BriefOutput, PlaybookOutput, RawDossier

_MODEL = "gpt-5"

_VOICE_TEMPLATE = """You are composing a private, elegantly printed one-pager for someone walking into a meeting with this company — either to interview there or to start work there soon.

Today's date is {today}. Anything dated after this is impossible; anything from this year is "recent".

Voice rules (obey strictly):
- Short sentences. Specific nouns. Concrete numbers where they exist.
- No marketing language. No "leading", "innovative", "world-class".
- No hedging. If you don't know something, omit the section rather than speculate.
- Write as if the reader is a ruthless peer short on time. Never patronize.
- If employee_reviews show discrepancies (e.g. good culture but terrible work-life balance), write a blunt 1-sentence culture_warning. Otherwise omit.

Invention discipline (CRITICAL — violations make the brief worthless):
- NEVER invent product names, model versions, customer names, dollar figures, dates, or any fact not present in the dossier.
- If the dossier says "GPT-5" do not write "GPT-4.x". If a customer isn't named in the dossier or web_snippets, do not name one.
- When uncertain about a specific name/number, write the general claim without it, or omit the line.

Data extraction rules (obey STRICTLY):
- `questions_to_ask`: EXACTLY 3 lethal, highly-specific questions grounded in dossier facts (a named recent hire, a specific funding round, a named competitor, a specific product). No generic interview questions.
- `how_they_talk`: Extract HOW they build — technical stacks, operational cadences, internal idioms — drawn from signals/web_snippets. DO NOT write their PR mission statement.
- `first_month_people`: Focus ONLY on specific context they own. DO NOT invent generic excuses like "align scope".
- `customers` / `customers_to_know`: Extract 3-5 named customers from the dossier (customers field, signals headlines, or web search snippets — the "customer case study" results are the richest source). For each, name what they use it for. If the dossier truly has none, omit the section — do not fabricate.
- `talent_signal`: Exactly 2 sentences interpreting the talent flow pattern for the candidate. Sentence 1: what the inbound pattern says about who joins and the implied culture (use hires.by_function). Sentence 2: what the outbound pattern says about where people go and what that implies about career trajectory (use departures.by_function). Use specific company names from the data. If both hires and departures are empty, omit this field entirely.

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
    # OpenAI structured output wants additionalProperties: false at every object level
    # and all properties listed in `required` — pydantic's default schema usually suffices.

    response = await client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": _voice()},
            {"role": "user", "content": _user_prompt(raw, role, mode)},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": schema_cls.__name__,
                "schema": schema,
                "strict": False,
            },
        },
    )
    content = response.choices[0].message.content or "{}"
    return json.loads(content)


async def synthesize_brief(raw: RawDossier, role: str) -> BriefOutput:
    data = await _synthesize(raw, role, "brief", BriefOutput)
    data.setdefault("company_name", raw.company.name)
    # Movement is structural — overwrite whatever the LLM produced with the
    # verbatim dossier data so users see ground truth, not a paraphrase.
    data["hires"] = raw.hires.model_dump()
    data["departures"] = raw.departures.model_dump()
    return BriefOutput.model_validate(data)


async def synthesize_playbook(raw: RawDossier, role: str) -> PlaybookOutput:
    data = await _synthesize(raw, role, "playbook", PlaybookOutput)
    data.setdefault("company_name", raw.company.name)
    data["hires"] = raw.hires.model_dump()
    data["departures"] = raw.departures.model_dump()

    if not data.get("shadow_org_chart") and raw.veterans:
        data["shadow_org_chart"] = [
            {"name": p.name, "title": p.title or "Unknown", "background": f"Joined: {p.tenure}" if p.tenure else "Long-tenured IC", "linkedin_url": p.linkedin_url}
            for p in raw.veterans
        ]
        
    return PlaybookOutput.model_validate(data)
