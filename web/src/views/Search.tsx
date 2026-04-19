import { useEffect, useRef, useState, type FormEvent } from "react";
import type { CompanyMatch, Mode } from "../types";
import { identifyCompany, prewarmCompany } from "../api";
import "./Search.css";

interface Props {
  onSubmit: (company: string, role: string, mode: Mode, domain?: string | null) => void;
}

export default function Search({ onSubmit }: Props) {
  const [mode, setMode] = useState<Mode>("brief");
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [matches, setMatches] = useState<CompanyMatch[]>([]);
  const [picked, setPicked] = useState<CompanyMatch | null>(null);
  const [matchesLoading, setMatchesLoading] = useState(false);
  const [highlighted, setHighlighted] = useState(0);
  const companyRef = useRef<HTMLInputElement>(null);
  const roleRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    companyRef.current?.focus();
  }, []);

  // Debounced typeahead. Cancels in-flight lookups when input changes.
  useEffect(() => {
    const q = company.trim();
    if (q.length < 2 || picked) {
      setMatches([]);
      setMatchesLoading(false);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setMatchesLoading(true);
      try {
        const resp = await identifyCompany(q, controller.signal);
        setMatches(resp.matches);
        setHighlighted(0);
      } catch (err) {
        if ((err as Error).name !== "AbortError") setMatches([]);
      } finally {
        setMatchesLoading(false);
      }
    }, 220);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [company, picked]);

  const showRole = !!picked;
  const canSubmit = !!picked && role.trim().length >= 2;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!canSubmit || !picked) return;
    onSubmit(picked.name, role.trim(), mode, picked.domain ?? null);
  };

  const pickMatch = (m: CompanyMatch) => {
    setPicked(m);
    setCompany(m.name);
    setMatches([]);
    // Warm the backend cache while the user types their role — saves 3-8s
    // off the final submit latency. Only fires when we have a domain.
    if (m.domain) prewarmCompany(m.name, m.domain);
    // Defer focus so layout (role field appearance) settles first.
    setTimeout(() => roleRef.current?.focus(), 0);
  };

  const onCompanyChange = (value: string) => {
    setCompany(value);
    if (picked && value !== picked.name) setPicked(null);
  };

  const onCompanyKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (matches.length === 0) {
      if (e.key === "Enter" && picked) {
        e.preventDefault();
        roleRef.current?.focus();
      }
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlighted((i) => Math.min(i + 1, matches.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlighted((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      pickMatch(matches[highlighted]);
    } else if (e.key === "Escape") {
      setMatches([]);
    }
  };

  const previewItems =
    mode === "brief"
      ? ["The moment", "The people", "Questions to ask"]
      : ["Your first month", "How they talk", "Questions to ask inside"];

  return (
    <main className="view search">
      <header className="search__brand">InsiderBrief</header>

      <div className="search__center">
        <section className="search__hero">
          <h1 className="search__headline">
            They researched you.
            <br />
            <em>Now research them.</em>
          </h1>
          <p className="search__sub">
            A private brief on any company &mdash; ready before your call.
          </p>
        </section>

        <form onSubmit={submit} className="search__form">
          <p className="search__prompt">
            Are you{" "}
            <button
              type="button"
              className={`search__mode ${mode === "brief" ? "is-active" : ""}`}
              onClick={() => setMode("brief")}
              aria-pressed={mode === "brief"}
            >
              meeting them
            </button>{" "}
            soon, or{" "}
            <button
              type="button"
              className={`search__mode ${mode === "playbook" ? "is-active" : ""}`}
              onClick={() => setMode("playbook")}
              aria-pressed={mode === "playbook"}
            >
              joining them
            </button>
            ?
          </p>

          <div className="search__field">
            <label htmlFor="company" className="search__label">
              {mode === "brief" ? "Who are you meeting with?" : "Where are you starting?"}
            </label>
            <div className="search__combo">
              <input
                id="company"
                ref={companyRef}
                className="search__input"
                value={company}
                onChange={(e) => onCompanyChange(e.target.value)}
                onKeyDown={onCompanyKeyDown}
                spellCheck={false}
                autoComplete="off"
                role="combobox"
                aria-expanded={matches.length > 0}
                aria-autocomplete="list"
              />
              {picked && (
                <span className="search__picked">
                  {picked.domain ? `· ${picked.domain}` : ""}
                </span>
              )}
              {matches.length > 0 && !picked && (
                <ul className="search__dropdown" role="listbox">
                  {matches.map((m, i) => (
                    <li
                      key={`${m.name}-${m.domain ?? i}`}
                      role="option"
                      aria-selected={i === highlighted}
                      className={`search__match ${i === highlighted ? "is-active" : ""}`}
                      onMouseEnter={() => setHighlighted(i)}
                      onMouseDown={(e) => {
                        e.preventDefault();
                        pickMatch(m);
                      }}
                    >
                      {m.logo_url ? (
                        <img
                          src={m.logo_url}
                          alt=""
                          className="search__match-logo"
                          loading="lazy"
                          onError={(e) => {
                            (e.currentTarget as HTMLImageElement).style.visibility = "hidden";
                          }}
                        />
                      ) : (
                        <span className="search__match-logo search__match-logo--blank" aria-hidden />
                      )}
                      <span className="search__match-body">
                        <span className="search__match-name">{m.name}</span>
                        <span className="search__match-meta">
                          {[m.domain, m.industry, m.employee_count_range]
                            .filter(Boolean)
                            .join(" · ")}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              {matchesLoading && matches.length === 0 && company.trim().length >= 2 && !picked && (
                <p className="search__hint">Looking&hellip;</p>
              )}
              {!matchesLoading && company.trim().length >= 2 && !picked && matches.length === 0 && (
                <p className="search__hint">No match yet. Keep typing.</p>
              )}
            </div>
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
              Read the brief &rarr;
            </button>
          </div>
        </form>

        <div className="search__preview" aria-label="What you'll get">
          <span className="search__preview-label">You&rsquo;ll walk away with</span>
          <ul className="search__preview-list">
            {previewItems.map((item, i) => (
              <li key={item}>
                {item}
                {i < previewItems.length - 1 && (
                  <span className="search__preview-sep" aria-hidden>
                    &middot;
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <footer className="search__footer">
        <span>Private. Composed in under a minute.</span>
      </footer>
    </main>
  );
}
