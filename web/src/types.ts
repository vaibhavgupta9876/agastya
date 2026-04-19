// Mirrors app/models/schemas.py — keep in sync by hand (small surface).

export type Mode = "brief" | "playbook";

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

export interface BriefOutput {
  company_name: string;
  essence: string;
  culture_warning?: string | null;
  moment: string[];
  people: BriefPerson[];
  role_survival: BriefPerson[];
  product: string;
  customers: string[];
  questions_to_ask: string[];
  hires: Movement;
  departures: Movement;
  talent_signal?: string | null;
}

export interface CustomerNote {
  name: string;
  note: string;
}

export interface ReadingItem {
  title: string;
  url: string;
}

export interface PlaybookOutput extends BriefOutput {
  first_month_people: BriefPerson[];
  shadow_org_chart: BriefPerson[];
  customers_to_know: CustomerNote[];
  the_bet: string;
  how_they_talk: string[];
  read_before_day_one: ReadingItem[];
}
