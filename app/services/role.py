"""
Cheap role classifier.

Runs in parallel with Crustdata fan-out so it adds zero wall-time latency.
Uses a small, fast model — this is cleanup work, not synthesis. Returns
None on any failure; dossier assembly must not fail because of this
enrichment.
"""

from __future__ import annotations

import json

from openai import AsyncOpenAI

from app.config import settings
from app.models.schemas import RoleClassification

_MODEL = "gpt-4o-mini"

_SYSTEM = """You classify a job role into structured context used to rank \
likely interviewers at a tech company.

Return ONLY JSON with these keys:
- family: the broad discipline in 2-4 words (e.g. "software engineering", \
"product management", "enterprise sales", "brand design", "ml research", \
"people/recruiting").
- seniority: one of ["IC", "senior IC", "lead/staff", "manager", "director", \
"VP+", "C-suite"]. Infer from the role text.
- likely_interviewer_titles: 4-6 job titles of people most likely to be in \
the interview loop for this role at a tech company. Include the direct \
manager, peers on the team, a cross-functional partner, and (for senior \
roles) a skip-level. Titles, not descriptions.

Return JSON only. No prose."""


async def classify_role(role: str) -> RoleClassification | None:
    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=20.0)
        resp = await client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": f'Role: "{role}"'},
            ],
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        family = str(data.get("family") or "").strip()
        seniority = str(data.get("seniority") or "").strip()
        titles_raw = data.get("likely_interviewer_titles") or []
        titles = [str(t).strip() for t in titles_raw if str(t).strip()]
        if not family:
            return None
        return RoleClassification(
            family=family,
            seniority=seniority,
            likely_interviewer_titles=titles[:6],
        )
    except Exception:
        return None
