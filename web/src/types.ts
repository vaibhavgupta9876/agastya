// Mirrors app/models/schemas.py — keep in sync by hand (small surface).

export type Mode = "brief" | "playbook";

export interface BriefPerson {
  name: string;
  title: string;
  background: string;
  linkedin_url?: string | null;
}

export interface BriefOutput {
  company_name: string;
  essence: string;
  moment: string[];
  people: BriefPerson[];
  product: string;
  customers: string[];
  questions_to_ask: string[];
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
  customers_to_know: CustomerNote[];
  the_bet: string;
  how_they_talk: string[];
  read_before_day_one: ReadingItem[];
}
