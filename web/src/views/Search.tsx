import { useEffect, useRef, useState, type FormEvent } from "react";
import type { Mode } from "../types";
import "./Search.css";

interface Props {
  onSubmit: (company: string, role: string, mode: Mode) => void;
}

export default function Search({ onSubmit }: Props) {
  const [mode, setMode] = useState<Mode>("brief");
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const companyRef = useRef<HTMLInputElement>(null);
  const roleRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    companyRef.current?.focus();
  }, []);

  const showRole = company.trim().length >= 3;
  const canSubmit = company.trim().length >= 2 && role.trim().length >= 2;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    onSubmit(company.trim(), role.trim(), mode);
  };

  return (
    <main className="view search">
      <header className="search__brand">InsiderBrief</header>

      <form onSubmit={submit} className="search__form">
        <p className="search__prompt">
          Are you{" "}
          <button
            type="button"
            className={`search__mode ${mode === "brief" ? "is-active" : ""}`}
            onClick={() => setMode("brief")}
          >
            meeting them
          </button>{" "}
          soon, or{" "}
          <button
            type="button"
            className={`search__mode ${mode === "playbook" ? "is-active" : ""}`}
            onClick={() => setMode("playbook")}
          >
            joining them
          </button>
          ?
        </p>

        <div className="search__field">
          <label htmlFor="company" className="search__label">
            {mode === "brief" ? "Who are you meeting with?" : "Where are you starting?"}
          </label>
          <input
            id="company"
            ref={companyRef}
            className="search__input"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && showRole) {
                e.preventDefault();
                roleRef.current?.focus();
              }
            }}
            spellCheck={false}
            autoComplete="off"
          />
        </div>

        <div
          className={`search__field search__field--role ${
            showRole ? "is-visible" : ""
          }`}
        >
          <label htmlFor="role" className="search__label">
            {mode === "brief"
              ? "What role are you interviewing for?"
              : "What role are you joining as?"}
          </label>
          <input
            id="role"
            ref={roleRef}
            className="search__input"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            spellCheck={false}
            autoComplete="off"
          />
        </div>

        <div
          className={`search__submit ${canSubmit ? "is-visible" : ""}`}
          aria-hidden={!canSubmit}
        >
          <button
            type="submit"
            disabled={!canSubmit}
            className="search__go"
          >
            Compose the brief →
          </button>
        </div>
      </form>

      <footer className="search__footer">
        <span>They researched you. Now research them.</span>
      </footer>
    </main>
  );
}
