# InsiderBrief

> Sales intelligence — but for the candidate.

Companies spend thousands on tools to research candidates before interviews. Candidates walk in with a LinkedIn tab and a prayer. **InsiderBrief** fixes that asymmetry.

Enter a company name and the role you're targeting. Get back a real-time intelligence dossier so you walk into every interview knowing more than the person across the table expects.

---

## The Problem

The hiring process is a two-way evaluation — but only one side has the data. Recruiters use tools like Crustdata to deeply understand candidates. Candidates are left Googling the company 30 minutes before the call. That gap costs candidates offers, and costs companies great hires who ghosted because they felt under-informed.

---

## What InsiderBrief Delivers

**Company Snapshot**
Funding stage, headcount trajectory, recent hires signal (growing vs. contracting), tech stack, and geographic footprint — pulled live so you're never reading stale Crunchbase.

**The People You'll Meet**
Profiles of the hiring manager, team leads, and key decision-makers: where they came from, what they've built, how long they've been at the company, and their public writing or posts.

**Product & Customer Intelligence**
What does the company actually sell? Who are their named customers? What's the ICP? Knowing this cold in an interview signals serious preparation.

**Live Company Signals**
Recent news, funding announcements, product launches, layoffs, or executive moves — the context that shapes every answer you give and every question you ask.

**AI-Generated Prep Sheet**
Tailored talking points, smart questions to ask (based on real company data), and flags to probe — generated from the dossier, not generic templates.

---

## API Surface (Crustdata)

| Endpoint | Used For |
|---|---|
| `POST /company/identify` | Resolve company name → structured profile |
| `POST /company/enrich` | Pull full company data: funding, headcount, customers, tech stack |
| `POST /person/search` | Find key people at the company by title/role |
| `POST /person/professional_network/enrich/live` | Live profiles for hiring manager + interviewers |
| `POST /web/search/live` | Recent news, press, product announcements |
| `POST /web/enrich/live` | Extract content from company blog / product pages |

---

## Demo Flow (6-minute walkthrough)

1. Enter: `"Sarvam AI"` + `"ML Engineer"`
2. InsiderBrief calls Crustdata — company identified, enriched, people pulled, web signals fetched
3. Output: a structured one-page dossier
   - Company is Series A, headcount grew 40% in 6 months → strong growth signal
   - Hiring manager joined from Google 8 months ago → ask about scaling culture shift
   - Recent blog post on speech models → tie your experience here
   - Two named enterprise customers in BFSI → know the domain before you walk in
4. Download as PDF or copy prep sheet to clipboard

---

## Why This Wins

- **Novel angle on a well-funded problem space** — recruiting tools are a top Crustdata use case, but this flips the direction
- **Immediately demo-able** — input one company name, output a real dossier in under 10 seconds
- **Real user pain** — everyone in the room has bombed an interview they could have aced with better prep
- **Defensible product surface** — extend to interview coaching, salary benchmarking, or recruiter outreach drafts

---

## Stack

- **Backend**: Python + FastAPI
- **AI layer**: Claude (Anthropic) for dossier synthesis and prep sheet generation
- **Data layer**: Crustdata APIs (all calls server-side, key never exposed)
- **Frontend**: Single-page React app, clean card-based output

---

## Tagline

*"They researched you. Now research them."*
