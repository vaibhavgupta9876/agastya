import type { PlaybookOutput } from "../types";
import MovementStrips from "../components/MovementStrips";
import "./Brief.css";
import "./Playbook.css";

interface Props {
  playbook: PlaybookOutput;
  onReset: () => void;
}

function SectionHead({ children }: { children: string }) {
  return <p className="sec__head">{children}</p>;
}

export default function Playbook({ playbook, onReset }: Props) {
  const hasMoment = playbook.moment && playbook.moment.length > 0;
  const hasPeople = playbook.people && playbook.people.length > 0;
  const hasCustomers = playbook.customers && playbook.customers.length > 0;
  const hasFirstMonth =
    playbook.first_month_people && playbook.first_month_people.length > 0;
  const hasCustomersToKnow =
    playbook.customers_to_know && playbook.customers_to_know.length > 0;
  const hasBet = playbook.the_bet && playbook.the_bet.trim().length > 0;
  const hasHowTheyTalk =
    playbook.how_they_talk && playbook.how_they_talk.length > 0;
  const hasReading =
    playbook.read_before_day_one && playbook.read_before_day_one.length > 0;
  const hasQuestions =
    playbook.questions_to_ask && playbook.questions_to_ask.length > 0;

  return (
    <main className="view brief playbook">
      <header className="brief__top">
        <span className="brief__brand">InsiderBrief</span>
        <button className="brief__back" onClick={onReset}>
          ← start again
        </button>
      </header>

      <article className="brief__doc">
        <p className="brief__meta">your playbook for joining</p>
        <h1 className="brief__company">{playbook.company_name}</h1>

        <section className="sec sec--essence">
          <p className="sec__essence">{playbook.essence}</p>
        </section>

        {hasBet && (
          <section className="sec">
            <SectionHead>The bet</SectionHead>
            <p className="sec__prose">{playbook.the_bet}</p>
          </section>
        )}

        {hasMoment && (
          <section className="sec">
            <SectionHead>The moment</SectionHead>
            <ul className="sec__moment">
              {playbook.moment.map((m, i) => (
                <li key={i}>{m}</li>
              ))}
            </ul>
          </section>
        )}

        <MovementStrips hires={playbook.hires} departures={playbook.departures} />

        <section className="sec">
          <SectionHead>The product</SectionHead>
          <p className="sec__prose">{playbook.product}</p>
        </section>

        {hasCustomers && (
          <section className="sec">
            <SectionHead>Who buys it</SectionHead>
            <p className="sec__prose">{playbook.customers.join(" · ")}</p>
          </section>
        )}

        {hasCustomersToKnow && (
          <section className="sec">
            <SectionHead>Customers to know</SectionHead>
            <ul className="sec__customers">
              {playbook.customers_to_know.map((c, i) => (
                <li key={i} className="customer">
                  <span className="customer__name">{c.name}</span>
                  <p className="customer__note">{c.note}</p>
                </li>
              ))}
            </ul>
          </section>
        )}

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

        {hasHowTheyTalk && (
          <section className="sec">
            <SectionHead>How they talk</SectionHead>
            <ul className="sec__moment">
              {playbook.how_they_talk.map((h, i) => (
                <li key={i}>{h}</li>
              ))}
            </ul>
          </section>
        )}

        {hasReading && (
          <section className="sec">
            <SectionHead>Read before day one</SectionHead>
            <ul className="sec__reading">
              {playbook.read_before_day_one.map((r, i) => (
                <li key={i}>
                  <a href={r.url} target="_blank" rel="noreferrer">
                    {r.title}
                  </a>
                </li>
              ))}
            </ul>
          </section>
        )}

        {hasQuestions && (
          <section className="sec">
            <SectionHead>Questions worth asking inside</SectionHead>
            <ol className="sec__questions">
              {playbook.questions_to_ask.map((q, i) => (
                <li key={i}>{q}</li>
              ))}
            </ol>
          </section>
        )}

        <footer className="brief__foot">
          <span>Composed for you. Walk in on day one like you've been here.</span>
        </footer>
      </article>
    </main>
  );
}
