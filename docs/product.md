# InsiderBrief — Product & Design

## The core insight

Hiring is a two-way evaluation, but only one side has the data. Companies spend thousands per seat on tools like Crustdata to deeply understand candidates. Candidates walk in with a LinkedIn tab and a prayer.

That asymmetry doesn't end at the offer letter — it just changes shape. Companies have onboarding playbooks for themselves. New joiners get a Notion link and a prayer.

InsiderBrief closes both gaps.

---

## Two candidates, two problems

The product serves one person at two distinct moments in their journey. The emotional state is different. The information need is different. The UI should flex accordingly.

### Applying / interviewing

> *"Don't let me sound stupid in 30 minutes."*

- **Horizon**: hours to days
- **Consumption**: once, then discarded
- **Needs**: distilled brief, specific things to reference, smart questions
- **Emotion**: anxiety masked as confidence
- **Failure mode today**: drowning in tabs — LinkedIn, Crunchbase, Glassdoor, company blog — with no time to synthesize

### Joined / joining

> *"Help me not waste my first 90 days."*

- **Horizon**: weeks to months
- **Consumption**: revisited repeatedly as a living workspace
- **Needs**: org map, who to meet (and in what order), product and customer fluency, strategic context, culture cues
- **Emotion**: quiet panic about ramp; impostor syndrome on day 1
- **Failure mode today**: 60-day ramp that should be 20 days; meeting the wrong people first; not recognizing customer names in calls

---

## Two modes, one product

Same core input (company + role). Same aesthetic. Different depth.

### Brief mode (applying)

A one-page editorial document. Sections in order of what a candidate actually needs, psychologically:

1. **One-sentence essence** — dissolves the "I don't really know what they do" anxiety
2. **The moment** — 1–2 live signals (recent funding, launches, exec moves) so they can reference something specific
3. **The people** — humanized profiles of likely interviewers
4. **The product** — concrete description of what they build and sell
5. **Who buys it** — customers and ICP
6. **Questions you could ask** — the killer feature; gives them a script

Read in 10 minutes. Feels like receiving an elegantly printed one-pager.

### Playbook mode (joining)

Same opening (essence, moment, product), but adds:

- **Your first month** — key people to meet, prioritized by role relevance. Sourced from Crustdata person search filtered by current title + company domain. Limited to what the API can surface: name, title, headline, LinkedIn URL.
- **Know these customers cold** — pulled from `company_data.competitors` (competitor company names/domains) in the company enrich response, giving named companies the candidate should recognize.
- **The bet** — what the company is wagering on right now, synthesized by Claude from `hiring.recent_titles_csv` (what roles they're backfilling), `headcount.growth_percent` (where they're growing), and web search signals.
- **How they talk** — pulled excerpts from company blog / eng posts via `web/enrich/live` page scraping.
- **What to read before day 1** — 3 specific links from web search results.

The Brief is a poem. The Playbook is a short book.

---

## Design principles

Aesthetic language: **Jony Ive × Japanese minimalism.** The product is a calm antidote to the anxious tab-hoarding it replaces.

- **Ma (間)** — negative space as meaningful. The page breathes.
- **Kanso (簡素)** — one meaningful thing at a time. No sidebars, no tabs, no chrome.
- **A document, not a dashboard** — editorial vertical flow, long measure, generous typography.
- **Serif for voice, sans for signal** — *Instrument Serif* for display, *Inter* for body.
- **Palette** — bone (`#FAFAF7`) background, charcoal (`#1A1A1A`) text, one muted grey for metadata. No blues, no accents.
- **Motion** — 400–600ms ease-out. Nothing bounces. Nothing spins.

---

## The three UX moments

### 1. Search

A quiet page. Centered. A single prompt:

> *"Are you meeting them soon, or joining them soon?"*

Two subtle choices. Then one hairline-underline input: the company name. Role appears as a second line only after the first is filled.

**Company name autocomplete** powered by `POST /company/search/autocomplete` (`field: "basic_info.name"`, free endpoint, no credits). This gives instant type-ahead with real company names before the user commits.

### 2. Thinking

No spinner. A single sentence fades in and out:

- *"Reading about Sarvam AI..."*
- *"Finding the people you'll meet..."*
- *"Assembling your brief."*

### 3. The output

A vertical document. Editorial type. Section headings are small and muted. Content is large and readable. It feels like a printed one-pager, not an app.

---

## Crustdata API surface — complete reference

### API version & auth

- **Base URL**: `https://api.crustdata.com`
- **Auth header**: `Authorization: Bearer <key>`
- **Version header**: `x-api-version: 2025-11-01`
- **Rate limit**: 15 requests/minute across most endpoints

### Company APIs

| Endpoint | Method | Purpose | Credits | Used in |
|---|---|---|---|---|
| `/company/search/autocomplete` | POST | Type-ahead for company names in the search input | **Free** | Search UX |
| `/company/identify` | POST | Resolve company name → `basic_info` (name, domain, employee range) | **Free** | Step 1: resolve user input |
| `/company/enrich` | POST | Full company profile with all `company_data` sections | 2 per record | Step 2: get everything |
| `/company/search` | POST | Filter-based company discovery (industry, funding, headcount) | 0.03 per result | Stretch: find similar companies |

#### Key `company_data` fields from `/company/enrich`

| Section | Fields | What it gives us |
|---|---|---|
| `basic_info` | `name`, `primary_domain`, `website`, `professional_network_url`, `year_founded`, `description`, `company_type`, `employee_count_range`, `industries` | **One-sentence essence** + core facts |
| `headcount` | `total`, `by_role_absolute`, `by_role_percent`, `by_region_absolute`, `growth_percent` | Team size, eng/sales/product breakdown, growth trajectory |
| `funding` | `total_investment_usd`, `last_round_amount_usd`, `last_fundraise_date`, `last_round_type`, `investors` | **The moment** (recent funding) + negotiation context |
| `locations` | `hq_country`, `hq_state`, `hq_city`, `headquarters` | Geographic context |
| `taxonomy` | `categories`, `professional_network_industry`, `professional_network_specialities` | Industry positioning |
| `revenue` | `estimated.lower_bound_usd`, `estimated.upper_bound_usd` | Scale context |
| `hiring` | `openings_count`, `openings_growth_percent`, `recent_titles_csv` | **The bet** — what roles they're investing in NOW |
| `followers` | `count`, `mom_percent`, `qoq_percent`, `yoy_percent` | Buzz/momentum signal |
| `seo` | `total_organic_results`, `monthly_organic_clicks`, `monthly_google_ads_budget` | Product maturity signal |
| `competitors` | `company_ids`, `websites` | **Know these customers cold** (competitive landscape) |
| `employee_reviews` | `overall_rating`, `culture_and_values_rating`, `work_life_balance_rating`, `review_count` | Culture signal — **new, not in current client** |
| `people` | `decision_makers`, `founders`, `cxos` | Key people embedded in company enrich — **free with the enrich call** |
| `news` | `article_url`, `article_title`, `article_publish_date` | Recent press — **free with the enrich call** |
| `software_reviews` | `review_count`, `average_rating` | Product quality signal (G2/Capterra equivalent) |
| `web_traffic` | `domain_traffic.monthly_visitors` | Product scale |
| `social_profiles` | `twitter_url` | Social presence |

> **Key discovery**: `/company/enrich` already returns `people.decision_makers`, `people.founders`, `people.cxos`, and `news` as part of the response. You don't need separate API calls for basic people and news data. Only call person search/enrich when you need deeper profiles (full experience, education, skills).

### Person APIs

| Endpoint | Method | Purpose | Credits | Used in |
|---|---|---|---|---|
| `/person/search` | POST | Find people at a company by title, name, location | 0.03 per result | Step 3: find interviewers |
| `/person/enrich` | POST | Full profile from LinkedIn URL or email | 1 per profile (+2 for contact, +2 for fresh fetch) | Step 4: enrich top people |
| `/person/search/autocomplete` | POST | Type-ahead for person filter values | **Free** | Not needed for MVP |

#### Key `person_data` fields from `/person/enrich`

| Section | Fields | What it gives us |
|---|---|---|
| `basic_profile` | `name`, `headline`, `current_title`, `summary`, `location`, `languages` | **The people** section |
| `professional_network` | `connections`, `followers`, `open_to_cards`, `profile_picture_permalink` | Influence signal, photo for UI |
| `experience.employment_details.current[]` | `company_name`, `title`, `start_date` | Current role context |
| `experience.employment_details.past[]` | `company_name`, `title`, `start_date`, `end_date` | Career trajectory |
| `education.schools[]` | School, degree, field | Shared background for talking points |
| `skills.professional_network_skills` | Skill keywords | Technical alignment |
| `social_handles` | `twitter_identifier.slug` | Social research |

#### Person search filter paths (corrected from quickstart docs)

Your current client uses `current_title` and `current_company.domain` — **these are wrong for the 2025-11-01 API version**. The correct fields are:

| What you want | Correct filter field | Operator |
|---|---|---|
| Current employer | `experience.employment_details.current.company_name` | `in` (array) |
| Current title | `experience.employment_details.current.title` | `(.)` (regex) |
| Any-time employer | `experience.employment_details.company_name` | `in` (array) |
| Any-time title | `experience.employment_details.title` | `(.)` (regex) |
| Location (country) | `basic_profile.location.country` | `=` |
| Location (geo radius) | `professional_network.location.raw` | `geo_distance` |

> **⚠️ This is a critical bug in your existing `crustdata.py` client.** The `search_people()` function uses `current_company.domain` and `current_title` — these will 400 with the v2025-11-01 API. Fix immediately.

### Web APIs

| Endpoint | Method | Purpose | Credits | Used in |
|---|---|---|---|---|
| `/web/search/live` | POST | Search the web for recent news, press, blog posts | TBD | Step 5: live signals |
| `/web/enrich/live` | POST | Extract full text content from a URL | TBD | Playbook: company voice |

---

## Data → brief section mapping

This table is the actual build spec. It maps each brief section to the exact API calls and fields needed.

### Brief mode

| Brief section | Data source | API call | Specific fields |
|---|---|---|---|
| **One-sentence essence** | Company enrich | `POST /company/enrich` with `domains: [domain]` | `basic_info.description`, `basic_info.industries`, `taxonomy.professional_network_specialities` |
| **The moment** | Company enrich + web search | Enrich: `news` section; Web: `POST /web/search/live` with `query: "{company_name} news"` | `news[].article_title`, `news[].article_publish_date`, `funding.last_round_type`, `funding.last_fundraise_date`, `funding.last_round_amount_usd` |
| **The people** | Company enrich + person search + person enrich | 1. `people.decision_makers` / `people.cxos` from company enrich (free). 2. `POST /person/search` with title regex for target role. 3. `POST /person/enrich` for top 3 LinkedIn URLs. | `basic_profile.name`, `basic_profile.headline`, `basic_profile.summary`, `experience.employment_details.past[]` |
| **The product** | Company enrich | Already from enrich | `basic_info.description`, `taxonomy.categories`, `seo` data |
| **Who buys it** | Company enrich | Already from enrich | `competitors.websites` (these are actually customer-adjacent companies), `taxonomy.professional_network_specialities` |
| **Questions to ask** | Claude synthesis | All raw data above → Claude prompt | Synthesize from funding timing, headcount growth, hiring patterns, interviewer backgrounds |

### Playbook mode (additional)

| Playbook section | Data source | API call | Specific fields |
|---|---|---|---|
| **First month people** | Person search (broader) | `POST /person/search` with `experience.employment_details.current.company_name` and various title regexes | Profiles for 8-12 people across functions |
| **The bet** | Company enrich | Already from enrich | `hiring.recent_titles_csv`, `headcount.growth_percent`, `headcount.by_role_absolute` |
| **How they talk** | Web enrich | `POST /web/enrich/live` on company blog URLs from web search | Extracted page text |
| **What to read** | Web search | `POST /web/search/live` with `"{company_name} engineering blog"` | Top 3 result URLs |
| **Culture cues** | Company enrich | Already from enrich | `employee_reviews.overall_rating`, `employee_reviews.culture_and_values_rating`, `employee_reviews.work_life_balance_rating` |

---

## APIs you're NOT using but SHOULD

### 1. Company Autocomplete — `POST /company/search/autocomplete` (**FREE**)
Use for the search input type-ahead. Field: `basic_info.name`. This is the polished UX touch that makes the demo feel professional.

### 2. `fields` parameter on enrich calls
Both company and person enrich accept a `fields` array. Instead of fetching the entire response, request only what you need. This potentially reduces response size and latency:
```json
{
  "domains": ["retool.com"],
  "fields": ["basic_info", "funding", "headcount", "hiring", "people", "news", "employee_reviews", "competitors"]
}
```

### 3. `employee_reviews` from company enrich
Free with the enrich call. Gives you Glassdoor-equivalent ratings without scraping. Perfect for the "culture cues" in Playbook mode.

### 4. `people.decision_makers` / `people.founders` / `people.cxos` from company enrich
These come embedded in the company enrich response. For Brief mode, you may not need a separate person search at all — the enrich already gives you the key people. Only call person search/enrich when you need deeper profiles or specific title matches.

### 5. `news[]` from company enrich
Recent articles already embedded in the enrich response. Reduces the need for a separate web search call for "The moment" section.

### 6. Person enrich with `force_fetch: true`
For the 2-3 key people you want the deepest data on, use `force_fetch: true` to get a real-time refresh of their LinkedIn profile. Costs +2 credits but ensures current data.

---

## Build order (hackathon)

1. **Crustdata client utility** — done, but needs filter path fix for person search.
2. **Dossier assembly service** — orchestrates the Crustdata calls in parallel, returns a raw dossier object.
3. **Claude synthesis layer** — takes the raw dossier, returns the structured written brief.
4. **`POST /dossier` route** — ties it together.
5. **Brief mode frontend** — the demo-friendly moment. Ship this.
6. **Playbook mode** — build if time. Otherwise, show the second option on the landing page as a roadmap signal.

The insight that wins this hackathon is *the asymmetry framing*, not the data volume. Brief mode is enough to demonstrate it. Playbook mode is the product's depth and the reason it isn't a one-trick demo.
