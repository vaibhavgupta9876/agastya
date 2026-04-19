# InsiderBrief — Handover

State as of commit `b819c9b` on `main`. Hackathon: ContextCon (Crustdata × YC, Bangalore, 6-hour build).

## What's built

End-to-end working. Verified against **Sarvam AI** and **Perplexity**.

- **Backend** (FastAPI, `app/`)
  - `services/crustdata.py` — 9 async endpoints, correct filter schema (single ConditionGroup `{op, conditions:[{field,type,value}]}`, not array).
  - `services/dossier.py` — parallel fan-out via `asyncio.gather`. Primary people source is `company_data.people` from `/company/enrich` (founders/decision_makers/cxos), augmented by `/person/search` and `/web/search/live`.
  - `services/synth.py` — GPT-5 via Chat Completions with `response_format: json_schema` (strict: false). Voice prompt enforces short specific sentences, no marketing, questions must reference concrete dossier points.
  - `main.py` — `/brief`, `/playbook`, `/health`. 180s timeout. CORS allows localhost:5173 and `agastya.pages.dev`.
- **Frontend** (`web/`, Vite + React + TS)
  - Views: Search → Thinking → Brief → Error. State machine in `App.tsx`.
  - Design: Instrument Serif + Inter, bone/charcoal/muted palette. Tokens in `src/styles/tokens.css`.
  - Vite proxy `/api/*` → `:8000/*`.

## Critical constants (don't relearn these)

- Crustdata base: `https://api.crustdata.com`, headers `Authorization: Bearer <key>`, `x-api-version: 2025-11-01`.
- Crustdata filter ops: `=, !=, <, =<, >, =>, in, not_in, (.), [.], geo_distance`. `(.)` is regex.
- `/company/enrich` **requires** `fields` param for rich payload — see `_COMPANY_ENRICH_FIELDS` in `crustdata.py`. Without it you only get `basic_info`.
- Person search: filter by `experience.employment_details.current.company_name` (use `=`), not `current_company.domain`. Title filter via `(.)` regex on `experience.employment_details.current.title`. We currently skip title filter (returned 0 rows) and let GPT-5 prioritize by role in the prompt.
- GPT-5 is slow (30–90s). AsyncOpenAI `timeout=180.0`, FastAPI `_TIMEOUT_SECONDS=180.0`. Don't lower these.

## Run locally

```bash
# backend
source .venv/bin/activate && uvicorn app.main:app --reload   # :8000
# frontend
cd web && npm run dev                                         # :5173
```

`.env` needs `CRUSTDATA_API_KEY` and `OPENAI_API_KEY`.

## Known gaps / stretch

- **Playbook frontend view not built.** Backend route `/playbook` works; `PlaybookOutput` schema + synth prompt exist. Frontend only renders Brief. Add `views/Playbook.tsx` mirroring `Brief.tsx` + extra sections (FirstMonth, CustomersToKnow, TheBet, HowTheyTalk, ReadBeforeDayOne) from the plan.
- **Streaming synthesis** (SSE) — not implemented. Thinking view uses rotating canned sentences instead.
- **Empty sections** — frontend hides empty arrays; confirm if a company returns thin data.
- **No tests.** Smoke-test via curl or the UI.

## Deploy

See `docs/deployment.md`. `Procfile` at repo root is for Render/Railway backend. Frontend is meant for `agastya.pages.dev` (already in CORS allow-list).

## Gotchas hit during build

- Crustdata person filters: the API wants `field` (not `filter_type`) and `filters` is a **single object**, not an array.
- Node 20.11 is on the edge of Vite 5 compatibility — scaffolding crashed once but files were already written; don't re-run `npm create vite`.
- User is on personal GitHub account `vaibhavgupta9876`, not the office account. Don't `git config` anything.

## Product thinking

`docs/product.md` has the full product framing — two modes (Brief for interviewing, Playbook for joining), aesthetic direction (Jony Ive × Japanese minimalism), and the Crustdata API reference the user extended. Read this before making UX changes.

The approved plan is at `/Users/weekday/.claude/plans/now-plan-the-full-polished-hare.md`.
