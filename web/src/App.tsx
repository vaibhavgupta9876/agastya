import { useEffect, useState } from "react";
import Search from "./views/Search";
import Thinking from "./views/Thinking";
import Brief from "./views/Brief";
import Playbook from "./views/Playbook";
import ErrorView from "./views/ErrorView";
import { fetchBrief, fetchPlaybook } from "./api";
import type { BriefOutput, Mode, PlaybookOutput } from "./types";

export interface BriefRequest {
  company: string;
  role: string;
  mode: Mode;
  domain: string | null;
}

type ViewState =
  | { kind: "search" }
  | { kind: "thinking"; company: string }
  | { kind: "brief"; brief: BriefOutput; req: BriefRequest }
  | { kind: "playbook"; playbook: PlaybookOutput; req: BriefRequest }
  | { kind: "error"; message: string };

function urlForRequest(req: BriefRequest): string {
  const params = new URLSearchParams({ c: req.company, r: req.role, m: req.mode });
  if (req.domain) params.set("d", req.domain);
  return `${window.location.origin}/?${params.toString()}`;
}

function readRequestFromUrl(): BriefRequest | null {
  const params = new URLSearchParams(window.location.search);
  const c = params.get("c");
  const r = params.get("r");
  const m = params.get("m");
  if (!c || !r || (m !== "brief" && m !== "playbook")) return null;
  return { company: c, role: r, mode: m, domain: params.get("d") };
}

export default function App() {
  const [view, setView] = useState<ViewState>({ kind: "search" });

  const runRequest = async (req: BriefRequest) => {
    setView({ kind: "thinking", company: req.company });
    // Keep the URL in sync so the current page is always shareable.
    const shareUrl = urlForRequest(req);
    window.history.replaceState(null, "", shareUrl);
    try {
      if (req.mode === "brief") {
        const brief = await fetchBrief(req.company, req.role, req.domain);
        setView({ kind: "brief", brief, req });
      } else {
        const playbook = await fetchPlaybook(req.company, req.role, req.domain);
        setView({ kind: "playbook", playbook, req });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setView({ kind: "error", message });
    }
  };

  const submit = (company: string, role: string, mode: Mode, domain?: string | null) =>
    runRequest({ company, role, mode, domain: domain ?? null });

  const reset = () => {
    window.history.replaceState(null, "", "/");
    setView({ kind: "search" });
  };

  // Auto-run from shareable URL on first load.
  useEffect(() => {
    const initial = readRequestFromUrl();
    if (initial) runRequest(initial);
  }, []);

  switch (view.kind) {
    case "search":
      return <Search onSubmit={submit} />;
    case "thinking":
      return <Thinking company={view.company} />;
    case "brief":
      return <Brief brief={view.brief} shareUrl={urlForRequest(view.req)} onReset={reset} />;
    case "playbook":
      return (
        <Playbook playbook={view.playbook} shareUrl={urlForRequest(view.req)} onReset={reset} />
      );
    case "error":
      return <ErrorView message={view.message} onReset={reset} />;
  }
}
