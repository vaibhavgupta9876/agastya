import type { BriefOutput } from "../types";
import MovementStrips from "../components/MovementStrips";
import "./Brief.css";

interface Props {
  brief: BriefOutput;
  onReset: () => void;
}

function SectionHead({ children }: { children: string }) {
  return <p className="sec__head">{children}</p>;
}

export default function Brief({ brief, onReset }: Props) {
  const hasCultureWarning = !!brief.culture_warning;

  // Cast or duck-type for PlaybookOutput specific fields
  const playbook = brief as any;
  const hasShadowOrgChart = playbook.shadow_org_chart && playbook.shadow_org_chart.length > 0;

  const hasFirstMonthPeople = playbook.first_month_people && playbook.first_month_people.length > 0;
  
  const hasMoment = brief.moment && brief.moment.length > 0;
  // Hide the generic Brief people section if we have the richer Playbook first_month_people
  const hasPeople = brief.people && brief.people.length > 0 && !hasFirstMonthPeople;
  const hasCustomers = brief.customers && brief.customers.length > 0;
  const hasQuestions = brief.questions_to_ask && brief.questions_to_ask.length > 0;

  return (
    <main className="view brief">
      <header className="brief__top">
        <span className="brief__brand">InsiderBrief</span>
        <button className="brief__back" onClick={onReset}>
          ← start again
        </button>
      </header>

      <article className="brief__doc">
        <p className="brief__meta">a private brief on</p>
        <h1 className="brief__company">{brief.company_name}</h1>

        <section className="sec sec--essence">
          <p className="sec__essence">{brief.essence}</p>
        </section>

        {hasCultureWarning && (
          <section className="sec sec--warning">
            <SectionHead>Culture Warning</SectionHead>
            <p className="sec__prose">{brief.culture_warning}</p>
          </section>
        )}

        {hasMoment && (
          <section className="sec">
            <SectionHead>The moment</SectionHead>
            <ul className="sec__moment">
              {brief.moment.map((m, i) => (
                <li key={i}>{m}</li>
              ))}
            </ul>
          </section>
        )}

        <MovementStrips hires={brief.hires} departures={brief.departures} talentSignal={brief.talent_signal} />

        {hasPeople && (
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
          <p className="sec__prose">{brief.product}</p>
        </section>

        {hasCustomers && (
          <section className="sec">
            <SectionHead>Who buys it</SectionHead>
            <p className="sec__prose">{brief.customers.join(" · ")}</p>
          </section>
        )}

        {hasQuestions && (
          <section className="sec">
            <SectionHead>Questions you could ask</SectionHead>
            <ol className="sec__questions">
              {brief.questions_to_ask.map((q, i) => (
                <li key={i}>{q}</li>
              ))}
            </ol>
          </section>
        )}

        <footer className="brief__foot">
          <span>Composed for you. Walk in knowing more than they expect.</span>
        </footer>
      </article>
    </main>
  );
}
