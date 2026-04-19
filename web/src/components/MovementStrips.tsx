import { useState } from "react";
import type { Movement, MovementPerson } from "../types";
import "./MovementStrips.css";

type Direction = "in" | "out";

interface Props {
  hires: Movement;
  departures: Movement;
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).slice(0, 2);
  return parts.map((p) => p[0]?.toUpperCase() ?? "").join("");
}

function formatDate(iso?: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return null;
  return d.toLocaleDateString(undefined, { month: "short", year: "numeric" });
}

function PersonRow({ person, direction }: { person: MovementPerson; direction: Direction }) {
  const dateStr = formatDate(person.event_date);
  const arrow = direction === "in" ? "←" : "→";
  return (
    <li className="mv-row">
      <div className="mv-row__avatar" aria-hidden="true">
        {initials(person.name)}
      </div>
      <div className="mv-row__body">
        <div className="mv-row__head">
          <span className="mv-row__name">
            {person.linkedin_url ? (
              <a href={person.linkedin_url} target="_blank" rel="noreferrer">
                {person.name}
              </a>
            ) : (
              person.name
            )}
          </span>
          {person.title && <span className="mv-row__title">{person.title}</span>}
        </div>
        {person.counterparty_company && (
          <div className="mv-row__counter">
            <span className="mv-row__arrow">{arrow}</span>
            <span className="mv-row__counter-co">{person.counterparty_company}</span>
            {person.counterparty_title && direction === "out" && (
              <span className="mv-row__counter-title">· {person.counterparty_title}</span>
            )}
          </div>
        )}
        {dateStr && <div className="mv-row__date">{dateStr}</div>}
      </div>
    </li>
  );
}

function Strip({
  label,
  movement,
  direction,
}: {
  label: string;
  movement: Movement;
  direction: Direction;
}) {
  const [open, setOpen] = useState(false);
  if (!movement || movement.people.length === 0) return null;

  const top = movement.people.slice(0, 6);
  const remaining = Math.max(0, movement.people.length - top.length);
  const counterparties = movement.by_function
    .filter((g) => g.function && g.function !== "Other / unknown")
    .slice(0, 4);
  const directionGlyph = direction === "in" ? "↘" : "↗";
  const directionWord = direction === "in" ? "from" : "to";

  return (
    <section className={`mv-strip mv-strip--${direction}`}>
      <button
        type="button"
        className="mv-strip__toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <header className="mv-strip__head">
          <span className="mv-strip__glyph" aria-hidden="true">
            {directionGlyph}
          </span>
          <span className="mv-strip__label">{label}</span>
          <span className="mv-strip__count">
            {movement.total.toLocaleString()} in last 12mo
          </span>
        </header>

        {counterparties.length > 0 && (
          <p className="mv-strip__summary">
            <span className="mv-strip__summary-prefix">{directionWord}</span>{" "}
            {counterparties.map((g, i) => (
              <span key={g.function}>
                <span className="mv-strip__chip">
                  {g.function}
                  {g.count > 1 && (
                    <span className="mv-strip__chip-count"> ×{g.count}</span>
                  )}
                </span>
                {i < counterparties.length - 1 && (
                  <span className="mv-strip__chip-sep"> · </span>
                )}
              </span>
            ))}
          </p>
        )}

        <div className="mv-strip__avatars" aria-hidden="true">
          {top.map((p, i) => (
            <span
              key={(p.linkedin_url || p.name) + i}
              className="mv-strip__avatar"
              title={`${p.name}${p.title ? " — " + p.title : ""}`}
            >
              {initials(p.name)}
            </span>
          ))}
          {remaining > 0 && (
            <span className="mv-strip__avatar mv-strip__avatar--more">
              +{remaining}
            </span>
          )}
          <span className="mv-strip__cta">{open ? "hide" : "see all"}</span>
        </div>
      </button>

      {open && (
        <ul className="mv-strip__list">
          {movement.people.map((p, i) => (
            <PersonRow
              key={(p.linkedin_url || p.name) + i}
              person={p}
              direction={direction}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

export default function MovementStrips({ hires, departures }: Props) {
  const hasHires = hires && hires.people.length > 0;
  const hasDepartures = departures && departures.people.length > 0;
  if (!hasHires && !hasDepartures) return null;

  return (
    <section className="sec mv-section">
      <p className="sec__head">Movement · last 12 months</p>
      <div className="mv-stack">
        {hasHires && <Strip label="Joining" movement={hires} direction="in" />}
        {hasDepartures && (
          <Strip label="Leaving" movement={departures} direction="out" />
        )}
      </div>
      <p className="mv-foot">
        Per most recent LinkedIn updates · sample of senior moves
      </p>
    </section>
  );
}
