import type {
  BriefOutput,
  IdentifyResponse,
  Mode,
  PlaybookOutput,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

async function post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
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

export function identifyCompany(
  query: string,
  signal?: AbortSignal,
): Promise<IdentifyResponse> {
  return post<IdentifyResponse>("/identify", { query }, signal);
}

/**
 * Fire-and-forget: tells the backend to start fetching the role-independent
 * dossier parts for a picked company, so the eventual /brief or /playbook
 * request hits a warm cache. Errors are swallowed — prewarm is best-effort.
 */
export function prewarmCompany(company: string, domain: string): void {
  post<unknown>("/prewarm", { company, domain }).catch(() => {
    // Best-effort only; the real submit will retry fully.
  });
}

export function fetchBrief(
  company: string,
  role: string,
  domain?: string | null,
): Promise<BriefOutput> {
  return post<BriefOutput>("/brief", {
    company,
    role,
    mode: "brief" as Mode,
    domain: domain ?? null,
  });
}

export function fetchPlaybook(
  company: string,
  role: string,
  domain?: string | null,
): Promise<PlaybookOutput> {
  return post<PlaybookOutput>("/playbook", {
    company,
    role,
    mode: "playbook" as Mode,
    domain: domain ?? null,
  });
}
