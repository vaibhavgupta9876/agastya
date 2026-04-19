# InsiderBrief — Dev Context

## Hackathon

- **Event**: ContextCon — first YC hackathon in Bangalore, hosted by Crustdata x Y Combinator
- **Format**: 6-hour build, working demo required
- **Prizes**: $8K / $3K / $1K + YC office hours (top 3) + Stripe Atlas waiver
- **Valid use cases**: sales intelligence, recruiting tools, market research, AI agents

## Crustdata API

- **Base URL**: `https://api.crustdata.com`
- **Auth header**: `Authorization: Bearer <key>`
- **Version header**: `x-api-version: 2025-11-01`
- **API key**: stored in `.env` as `CRUSTDATA_API_KEY`

### Endpoints we use

| Endpoint | Purpose |
|---|---|
| `POST /company/identify` | Resolve company name → domain + structured ID |
| `POST /company/enrich` | Full company profile (funding, headcount, customers, tech stack) |
| `POST /person/search` | Find people at a company by title/role |
| `POST /person/professional_network/enrich/live` | Live profiles for key people |
| `POST /web/search/live` | Recent news, press, product announcements |
| `POST /web/enrich/live` | Extract content from specific URLs |

## Product goal

The core loop:
1. Candidate inputs company name + target role
2. Backend calls Crustdata to build a raw dossier (company + people + signals)
3. Claude synthesizes into a structured prep brief
4. Frontend renders as a clean one-page card

## Build priorities (hackathon order)

1. Crustdata client utility (`app/services/crustdata.py`) ← start here
2. Dossier assembly service that orchestrates the API calls
3. Claude synthesis layer
4. FastAPI route: `POST /dossier`
5. Minimal frontend
