import type { BriefOutput, Mode, PlaybookOutput } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch {}
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export function fetchBrief(company: string, role: string): Promise<BriefOutput> {
  return post<BriefOutput>("/brief", { company, role, mode: "brief" as Mode });
}

export function fetchPlaybook(
  company: string,
  role: string,
): Promise<PlaybookOutput> {
  return post<PlaybookOutput>("/playbook", {
    company,
    role,
    mode: "playbook" as Mode,
  });
}
