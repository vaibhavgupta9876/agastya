# InsiderBrief

*"They researched you. Now research them."*

InsiderBrief gives job candidates the same intelligence edge that companies have. Enter a company name and the role you're targeting — get back a real-time dossier on the company, its key people, product, customers, and recent signals.

## What it does

- **Company snapshot** — funding stage, headcount growth, tech stack, geographic presence
- **People intelligence** — profiles of hiring managers, team leads, and decision-makers
- **Product & customer context** — what they sell, who they sell it to, their ICP
- **Live signals** — recent news, launches, funding, executive moves
- **AI prep sheet** — tailored talking points and smart questions generated from the dossier

## Stack

- **Backend**: Python, FastAPI
- **Data**: [Crustdata APIs](https://docs.crustdata.com) — company, person, and web endpoints
- **AI**: Claude (Anthropic) for dossier synthesis
- **Frontend**: React

## Getting started

```bash
cp .env.example .env
# fill in CRUSTDATA_API_KEY and ANTHROPIC_API_KEY

pip install -r requirements.txt
uvicorn app.main:app --reload
```

API available at `http://localhost:8000`. Docs at `http://localhost:8000/docs`.

## Project structure

```
app/
├── main.py              # FastAPI app and routes
├── config.py            # Settings from env
├── services/
│   └── crustdata.py     # Crustdata API client
└── models/
    └── schemas.py       # Request/response types
```
