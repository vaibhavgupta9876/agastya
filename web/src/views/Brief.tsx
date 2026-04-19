import { useState } from "react";
import type { BriefOutput, Source, Sourced } from "../types";
import MovementStrips from "../components/MovementStrips";
import HeadcountStrip from "../components/HeadcountStrip";
import "./Brief.css";

interface Props {
  brief: BriefOutput;
  shareUrl: string;
  onReset: () => void;
}

function ShareButton({ url }: { url: string }) {
  const [copied, setCopied] = useState(false);
  const onClick = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      window.prompt("Copy this link:", url);
    }
  };
  return (
    <button className="brief__share" onClick={onClick} type="button">
      {copied ? "link copied" : "share"}
    </button>
  );
}

function SectionHead({ children }: { children: string }) {
  return <p className="sec__head">{children}</p>;
}

function SectionEmpty({ children }: { children: string }) {
  return <p className="sec__empty">{children}</p>;
}

function Receipts({ sources }: { sources: Source[] | undefined }) {
  if (!sources || sources.length === 0) return null;
  return (
    <span className="receipts">
      {sources.map((s, i) => (
        <a
          key={i}
          href={s.url}
          target="_blank"
          rel="noreferrer"
          className="receipts__chip"
          title={s.title || s.url}
        >
          {i + 1}
        </a>
      ))}
    </span>
  );
}

export default function Brief({ brief, shareUrl, onReset }: Props) {
  const playbook = brief as any;
  const hasShadowOrgChart = playbook.shadow_org_chart && playbook.shadow_org_chart.length > 0;
  const hasFirstMonthPeople = playbook.first_month_people && playbook.first_month_people.length > 0;
  // Hide the generic Brief people section if we have the richer Playbook first_month_people
  const showGenericPeople = brief.people && brief.people.length > 0 && !hasFirstMonthPeople;

  const emptyText = (s: Sourced | null | undefined): string => (s && s.text ? s.text : "");
  const essenceText = emptyText(brief.essence);
  const productText = emptyText(brief.product);

  return (
    <main className="view brief">
      <header className="brief__top">
        <span className="brief__brand">InsiderBrief</span>
        <div className="brief__actions">
          <ShareButton url={shareUrl} />
          <button className="brief__back" onClick={onReset}>
            ← start again
          </button>
        </div>
      </header>

      <article className="brief__doc">
        <p className="brief__meta">a private brief on</p>
        <h1 className="brief__company">{brief.company_name}</h1>

        <section className="sec sec--essence">
          {essenceText ? (
            <p className="sec__essence">
              {essenceText}
              <Receipts sources={brief.essence?.sources} />
            </p>
          ) : (
            <SectionEmpty>
              The dossier didn't surface a clean one-line description.
            </SectionEmpty>
          )}
        </section>

        <section className="sec sec--warning">
          <SectionHead>Culture Warning</SectionHead>
          {brief.culture_warning && brief.culture_warning.text ? (
            <p className="sec__prose">
              {brief.culture_warning.text}
              <Receipts sources={brief.culture_warning.sources} />
            </p>
          ) : (
            <SectionEmpty>
              No contradictions surfaced between the public story and employee reviews.
            </SectionEmpty>
          )}
        </section>

        <section className="sec">
          <SectionHead>The moment</SectionHead>
          {brief.moment && brief.moment.length > 0 ? (
            <ul className="sec__moment">
              {brief.moment.map((m, i) => (
                <li key={i}>
                  {m.text}
                  <Receipts sources={m.sources} />
                </li>
              ))}
            </ul>
          ) : (
            <SectionEmpty>No recent signals surfaced in the last 90 days.</SectionEmpty>
          )}
        </section>

        <MovementStrips hires={brief.hires} departures={brief.departures} talentSignal={brief.talent_signal?.text ?? null} />

        <HeadcountStrip trends={brief.headcount_trends ?? []} />

        {showGenericPeople && (
          <section className="sec">
            <SectionHead>The people</SectionHead>
            <ul className="sec__people">
              {brief.people.map((p, i) => (
                <li key={i} className="person">
                  <div className="person__head">
                    <span className="person__name">
                      {p.linkedin_url ? (
                        <a href={p.linkedin_url} target="_blank" rel="noreferrer">
                          {p.name}
                        </a>
                      ) : (
                        p.name
                      )}
                    </span>
                    <span className="person__title">{p.title}</span>
                  </div>
                  <p className="person__bg">{p.background}</p>
                </li>
              ))}
            </ul>
          </section>
        )}

        {hasFirstMonthPeople && (
          <section className="sec sec--playbook">
            <SectionHead>The Fresh Blood (Meet your first month)</SectionHead>
            <ul className="sec__people">
              {playbook.first_month_people.map((p: any, i: number) => (
                <li key={i} className="person">
                  <div className="person__head">
                    <span className="person__name">
                      {p.linkedin_url ? (
                        <a href={p.linkedin_url} target="_blank" rel="noreferrer">
                          {p.name}
                        </a>
                      ) : (
                        p.name
                      )}
                    </span>
                    <span className="person__title">{p.title}</span>
                  </div>
                  <p className="person__bg">{p.background}</p>
                </li>
              ))}
            </ul>
          </section>
        )}

        {hasShadowOrgChart && (
          <section className="sec sec--shadow">
            <SectionHead>Institutional Memory (The Shadow Org Chart)</SectionHead>
            <ul className="sec__people">
              {playbook.shadow_org_chart.map((p: any, i: number) => (
                <li key={i} className="person">
                  <div className="person__head">
                    <span className="person__name">
                      {p.linkedin_url ? (
                        <a href={p.linkedin_url} target="_blank" rel="noreferrer">
                          {p.name}
                        </a>
                      ) : (
                        p.name
                      )}
                    </span>
                    <span className="person__title">{p.title}</span>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className="sec">
          <SectionHead>The product</SectionHead>
          {productText ? (
            <p className="sec__prose">
              {productText}
              <Receipts sources={brief.product?.sources} />
            </p>
          ) : (
            <SectionEmpty>The dossier didn't yield a clear product description.</SectionEmpty>
          )}
        </section>

        <section className="sec">
          <SectionHead>Who buys it</SectionHead>
          {brief.customers && brief.customers.length > 0 ? (
            <ul className="sec__customers">
              {brief.customers.map((c, i) => (
                <li key={i}>
                  {c.text}
                  <Receipts sources={c.sources} />
                </li>
              ))}
            </ul>
          ) : (
            <SectionEmpty>
              No named customers or public case studies surfaced. Worth asking directly.
            </SectionEmpty>
          )}
        </section>

        <section className="sec">
          <SectionHead>Questions you could ask</SectionHead>
          {brief.questions_to_ask && brief.questions_to_ask.length > 0 ? (
            <ol className="sec__questions">
              {brief.questions_to_ask.map((q, i) => (
                <li key={i}>{q}</li>
              ))}
            </ol>
          ) : (
            <SectionEmpty>Not enough dossier signal to ground specific questions.</SectionEmpty>
          )}
        </section>

        <footer className="brief__foot">
          <span>Composed for you. Walk in knowing more than they expect.</span>
        </footer>
      </article>
    </main>
  );
}
