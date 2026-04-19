// Mirrors app/models/schemas.py — keep in sync by hand (small surface).

export type Mode = "brief" | "playbook";

export interface Source {
  url: string;
  title?: string | null;
  date?: string | null;
}

export interface Sourced {
  text: string;
  sources: Source[];
}

export interface CompanyMatch {
  name: string;
  domain?: string | null;
  logo_url?: string | null;
  industry?: string | null;
  employee_count_range?: string | null;
  linkedin_url?: string | null;
}

export interface IdentifyResponse {
  matches: CompanyMatch[];
}

export interface BriefPerson {
  name: string;
  title: string;
  background: string;
  linkedin_url?: string | null;
}

export interface MovementPerson {
  name: string;
  title?: string | null;
  headline?: string | null;
  linkedin_url?: string | null;
  function_category?: string | null;
  seniority_level?: string | null;
  event_date?: string | null;
  counterparty_company?: string | null;
  counterparty_title?: string | null;
}

export interface MovementGroup {
  function: string;
  count: number;
}

export interface Movement {
  total: number;
  people: MovementPerson[];
  by_function: MovementGroup[];
}

export interface HeadcountTrend {
  function: string;
  share_pct?: number | null;
  current_count?: number | null;
  yoy_pct?: number | null;
  hiring_qoq_pct?: number | null;
}

export interface BriefOutput {
  company_name: string;
  essence: Sourced;
  culture_warning?: Sourced | null;
  moment: Sourced[];
  people: BriefPerson[];
  role_survival: BriefPerson[];
  product: Sourced;
  customers: Sourced[];
  questions_to_ask: string[];
  hires: Movement;
  departures: Movement;
  talent_signal?: Sourced | null;
  headcount_trends: HeadcountTrend[];
}

export interface CustomerNote {
  name: string;
  note: string;
  sources: Source[];
}

export interface ReadingItem {
  title: string;
  url: string;
}

export interface PlaybookOutput extends BriefOutput {
  first_month_people: BriefPerson[];
  shadow_org_chart: BriefPerson[];
  customers_to_know: CustomerNote[];
  the_bet?: Sourced | null;
  how_they_talk: Sourced[];
  read_before_day_one: ReadingItem[];
}
