import { useState } from "react";
import Search from "./views/Search";
import Thinking from "./views/Thinking";
import Brief from "./views/Brief";
import Playbook from "./views/Playbook";
import ErrorView from "./views/ErrorView";
import { fetchBrief, fetchPlaybook } from "./api";
import type { BriefOutput, Mode, PlaybookOutput } from "./types";

type ViewState =
  | { kind: "search" }
  | { kind: "thinking"; company: string }
  | { kind: "brief"; brief: BriefOutput }
  | { kind: "playbook"; playbook: PlaybookOutput }
  | { kind: "error"; message: string };

export default function App() {
  const [view, setView] = useState<ViewState>({ kind: "search" });

  const submit = async (company: string, role: string, mode: Mode) => {
    setView({ kind: "thinking", company });
    try {
      if (mode === "brief") {
        const brief = await fetchBrief(company, role);
        setView({ kind: "brief", brief });
      } else {
        const playbook = await fetchPlaybook(company, role);
        setView({ kind: "playbook", playbook });
      }
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Something went wrong.";
      setView({ kind: "error", message });
    }
  };

  const reset = () => setView({ kind: "search" });

  switch (view.kind) {
    case "search":
      return <Search onSubmit={submit} />;
    case "thinking":
      return <Thinking company={view.company} />;
    case "brief":
      return <Brief brief={view.brief} onReset={reset} />;
    case "playbook":
      return <Playbook playbook={view.playbook} onReset={reset} />;
    case "error":
      return <ErrorView message={view.message} onReset={reset} />;
  }
}
