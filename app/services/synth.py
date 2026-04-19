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

from openai import AsyncOpenAI

from app.config import settings
from app.models.schemas import BriefOutput, PlaybookOutput, RawDossier

_MODEL = "gpt-5"

_VOICE = """You are composing a private, elegantly printed one-pager for someone walking into a meeting with this company — either to interview there or to start work there soon.

Voice rules (obey strictly):
- Short sentences. Specific nouns. Concrete numbers where they exist.
- No marketing language. No "leading", "innovative", "cutting-edge", "world-class".
- No hedging. If you don't know something, omit the section rather than speculate.
- Write as if the reader is smart and short on time. Never patronize.
- For questions_to_ask, each one must reference a SPECIFIC data point from the dossier — a funding round, a named product, a customer, a hiring signal, a person by name. Generic interview questions are a failure.
- For the essence, one sentence. It should make someone who doesn't know the company immediately understand what they sell and to whom.

Return ONLY valid JSON matching the schema provided. No preamble, no trailing prose."""


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
            {"role": "system", "content": _VOICE},
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
    return BriefOutput.model_validate(data)


async def synthesize_playbook(raw: RawDossier, role: str) -> PlaybookOutput:
    data = await _synthesize(raw, role, "playbook", PlaybookOutput)
    data.setdefault("company_name", raw.company.name)
    return PlaybookOutput.model_validate(data)
