import { useState } from "react";
import type { PlaybookOutput, Source, Sourced } from "../types";
import MovementStrips from "../components/MovementStrips";
import HeadcountStrip from "../components/HeadcountStrip";
import "./Brief.css";
import "./Playbook.css";

interface Props {
  playbook: PlaybookOutput;
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

const textOf = (s: Sourced | null | undefined): string => (s && s.text ? s.text : "");

export default function Playbook({ playbook, shareUrl, onReset }: Props) {
  const hasPeople = playbook.people && playbook.people.length > 0;
  const hasFirstMonth =
    playbook.first_month_people && playbook.first_month_people.length > 0;

  const essenceText = textOf(playbook.essence);
  const productText = textOf(playbook.product);
  const betText = textOf(playbook.the_bet);

  return (
    <main className="view brief playbook">
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
        <p className="brief__meta">your playbook for joining</p>
        <h1 className="brief__company">{playbook.company_name}</h1>

        <section className="sec sec--essence">
          {essenceText ? (
            <p className="sec__essence">
              {essenceText}
              <Receipts sources={playbook.essence?.sources} />
            </p>
          ) : (
            <SectionEmpty>The dossier didn't surface a clean one-line description.</SectionEmpty>
          )}
        </section>

        <section className="sec">
          <SectionHead>The bet</SectionHead>
          {betText ? (
            <p className="sec__prose">
              {betText}
              <Receipts sources={playbook.the_bet?.sources} />
            </p>
          ) : (
            <SectionEmpty>No clear strategic bet surfaced from public signals.</SectionEmpty>
          )}
        </section>

        <section className="sec">
          <SectionHead>The moment</SectionHead>
          {playbook.moment && playbook.moment.length > 0 ? (
            <ul className="sec__moment">
              {playbook.moment.map((m, i) => (
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

        <MovementStrips hires={playbook.hires} departures={playbook.departures} talentSignal={playbook.talent_signal?.text ?? null} />

        <HeadcountStrip trends={playbook.headcount_trends ?? []} />

        <section className="sec">
          <SectionHead>The product</SectionHead>
          {productText ? (
            <p className="sec__prose">
              {productText}
              <Receipts sources={playbook.product?.sources} />
            </p>
          ) : (
            <SectionEmpty>The dossier didn't yield a clear product description.</SectionEmpty>
          )}
        </section>

        <section className="sec">
          <SectionHead>Who buys it</SectionHead>
          {playbook.customers && playbook.customers.length > 0 ? (
            <ul className="sec__customers">
              {playbook.customers.map((c, i) => (
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
          <SectionHead>Customers to know</SectionHead>
          {playbook.customers_to_know && playbook.customers_to_know.length > 0 ? (
            <ul className="sec__customers">
              {playbook.customers_to_know.map((c, i) => (
                <li key={i} className="customer">
                  <span className="customer__name">{c.name}</span>
                  <Receipts sources={c.sources} />
                  <p className="customer__note">{c.note}</p>
                </li>
              ))}
            </ul>
          ) : (
            <SectionEmpty>No deep customer case studies found. Ask sales or CS for one.</SectionEmpty>
          )}
        </section>

        {hasPeople && (
          <section className="sec">
            <SectionHead>The people</SectionHead>
            <ul className="sec__people">
              {playbook.people.map((p, i) => (
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

        {hasFirstMonth && (
          <section className="sec">
            <SectionHead>Meet in your first month</SectionHead>
            <ul className="sec__people">
              {playbook.first_month_people.map((p, i) => (
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

        <section className="sec">
          <SectionHead>How they talk</SectionHead>
          {playbook.how_they_talk && playbook.how_they_talk.length > 0 ? (
            <ul className="sec__moment">
              {playbook.how_they_talk.map((h, i) => (
                <li key={i}>
                  {h.text}
                  <Receipts sources={h.sources} />
                </li>
              ))}
            </ul>
          ) : (
            <SectionEmpty>No distinctive internal idioms or stack details surfaced.</SectionEmpty>
          )}
        </section>

        <section className="sec">
          <SectionHead>Read before day one</SectionHead>
          {playbook.read_before_day_one && playbook.read_before_day_one.length > 0 ? (
            <ul className="sec__reading">
              {playbook.read_before_day_one.map((r, i) => (
                <li key={i}>
                  <a href={r.url} target="_blank" rel="noreferrer">
                    {r.title}
                  </a>
                </li>
              ))}
            </ul>
          ) : (
            <SectionEmpty>No standout reading list emerged from public signals.</SectionEmpty>
          )}
        </section>

        <section className="sec">
          <SectionHead>Questions worth asking inside</SectionHead>
          {playbook.questions_to_ask && playbook.questions_to_ask.length > 0 ? (
            <ol className="sec__questions">
              {playbook.questions_to_ask.map((q, i) => (
                <li key={i}>{q}</li>
              ))}
            </ol>
          ) : (
            <SectionEmpty>Not enough dossier signal to ground specific questions.</SectionEmpty>
          )}
        </section>

        <footer className="brief__foot">
          <span>Composed for you. Walk in on day one like you've been here.</span>
        </footer>
      </article>
    </main>
  );
}
