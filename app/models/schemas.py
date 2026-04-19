"""
End-to-end typed schemas for InsiderBrief.

Three layers:
    1. Request in    — what the frontend sends
    2. RawDossier    — what our dossier service assembles from Crustdata
    3. Brief/Playbook Output — what GPT-5 synthesizes and the frontend renders

The RawDossier is deliberately flatter than the Crustdata response; we strip
the bits we don't need before handing it to the LLM so the prompt stays tight.
"""

from typing import Literal

from pydantic import BaseModel, Field

Mode = Literal["brief", "playbook"]


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class DossierRequest(BaseModel):
    company: str = Field(..., min_length=1, description="Company name as typed by the user")
    role: str = Field(..., min_length=1, description="Role the candidate is applying to or joining")
    mode: Mode = "brief"


# ---------------------------------------------------------------------------
# Raw dossier (Crustdata → normalized)
# ---------------------------------------------------------------------------


class CompanySnapshot(BaseModel):
    name: str
    domain: str | None = None
    website: str | None = None
    description: str | None = None
    year_founded: str | None = None
    company_type: str | None = None
    employee_count_range: str | None = None
    headcount_total: int | None = None
    headcount_growth_percent: float | None = None
    industries: list[str] = []
    hq_location: str | None = None

    funding_total_usd: float | None = None
    last_round_amount_usd: float | None = None
    last_round_type: str | None = None
    last_fundraise_date: str | None = None
    investors: list[str] = []

    hiring_openings_count: int | None = None
    hiring_recent_titles: list[str] = []

    competitors: list[str] = []
    customers: list[str] = []
    employee_reviews: dict | None = None


class PersonCard(BaseModel):
    name: str
    title: str | None = None
    headline: str | None = None
    linkedin_url: str | None = None
    tenure: str | None = None
    location: str | None = None


class Signal(BaseModel):
    headline: str
    url: str | None = None
    published_at: str | None = None
    summary: str | None = None


class MovementPerson(BaseModel):
    """A single person inside a hires/departures strip."""

    name: str
    title: str | None = None
    headline: str | None = None
    linkedin_url: str | None = None
    function_category: str | None = None
    seniority_level: str | None = None
    # For hires: when they joined target; for departures: when they left target.
    event_date: str | None = None
    # For hires: where they came from. For departures: where they went.
    counterparty_company: str | None = None
    counterparty_title: str | None = None


class MovementGroup(BaseModel):
    """Aggregate function-bucket counts for the strip's summary line."""

    function: str
    count: int


class Movement(BaseModel):
    total: int = 0
    people: list[MovementPerson] = []
    by_function: list[MovementGroup] = []


class RawDossier(BaseModel):
    """What we hand to GPT-5 for synthesis."""

    company: CompanySnapshot
    people: list[PersonCard] = []
    signals: list[Signal] = []
    web_snippets: list[str] = []
    veterans: list[PersonCard] = []
    alumni_in_role: list[PersonCard] = []
    hires: Movement = Field(default_factory=Movement)
    departures: Movement = Field(default_factory=Movement)


# ---------------------------------------------------------------------------
# Synthesized output
# ---------------------------------------------------------------------------


class BriefPerson(BaseModel):
    name: str
    title: str
    background: str
    linkedin_url: str | None = None


class BriefOutput(BaseModel):
    """What Brief mode renders."""

    company_name: str
    essence: str
    culture_warning: str | None = Field(default=None, description="1 short warning if employee reviews contradict marketing")
    moment: list[str] = Field(default_factory=list, description="1-2 recent signals worth referencing")
    people: list[BriefPerson] = []
    role_survival: list[BriefPerson] = Field(default_factory=list, description="People who recently left the target role")
    product: str
    customers: list[str] = Field(default_factory=list, description="Customer name + specific use case. Focus on depth over volume.")
    questions_to_ask: list[str] = Field(
        default_factory=list, 
        description="EXACTLY 3 lethal, highly-specific questions. E.g. asking about trade-offs, tech debt, or a recent failure."
    )
    # Structural movement data — passed through from RawDossier verbatim,
    # not synthesized by the LLM. The LLM may reference it in questions.
    hires: Movement = Field(default_factory=Movement)
    departures: Movement = Field(default_factory=Movement)


class CustomerNote(BaseModel):
    name: str
    note: str


class ReadingItem(BaseModel):
    title: str
    url: str


class PlaybookOutput(BriefOutput):
    """What Playbook mode renders — everything in Brief plus the joining-specific sections."""

    first_month_people: list[BriefPerson] = []
    shadow_org_chart: list[BriefPerson] = Field(default_factory=list, description="Longest tenured ICs (not VPs/CXOs)")
    customers_to_know: list[CustomerNote] = Field(default_factory=list, description="Top 2 customers and how they actually use the product.")
    the_bet: str = Field(default="", description="The core strategic gamble the company is making right now.")
    how_they_talk: list[str] = Field(
        default_factory=list, 
        description="Internal idioms, operational cadences, or technical stack context. IGNORE PR/MARKETING SPEAK (e.g. 'Safety first', 'Expanding access')."
    )
    read_before_day_one: list[ReadingItem] = []
