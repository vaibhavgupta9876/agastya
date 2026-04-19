import { useEffect, useState } from "react";
import "./Thinking.css";

interface Props {
  company: string;
}

/**
 * Three phases that roughly track the real backend pipeline.
 * Timings are approximate — the view keeps cycling inside the final phase
 * indefinitely, so a slow run never "parks" on a dead line.
 */
const phase = (company: string) => ({
  gathering: [
    `Reading about ${company}\u2026`,
    `Pulling the company record\u2026`,
    `Scanning recent news\u2026`,
    `Locating the primary domain\u2026`,
  ],
  probing: [
    `Who joined ${company} in the last year\u2026`,
    `Where people leave ${company} to\u2026`,
    `Reading employee notes on Glassdoor\u2026`,
    `Skimming Blind for the inside story\u2026`,
    `Looking for founder interviews\u2026`,
    `Finding the people you\u2019ll meet\u2026`,
  ],
  composing: [
    `Assembling your brief\u2026`,
    `Picking the moment that matters\u2026`,
    `Cutting the marketing language\u2026`,
    `Citing the sources\u2026`,
    `Writing questions worth asking\u2026`,
    `One more pass for specificity\u2026`,
    `Almost there\u2026`,
  ],
});

const fmtElapsed = (sec: number) => {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
};

export default function Thinking({ company }: Props) {
  const lines = phase(company);
  const [elapsed, setElapsed] = useState(0);
  const [lineIndex, setLineIndex] = useState(0);

  // 1hz elapsed ticker
  useEffect(() => {
    const id = window.setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => window.clearInterval(id);
  }, []);

  // Sentence rotation — new line every 3.2s, loops inside current phase forever.
  useEffect(() => {
    const id = window.setInterval(() => setLineIndex((i) => i + 1), 3200);
    return () => window.clearInterval(id);
  }, []);

  // Phase selection by elapsed time (roughly matches pipeline stages).
  const currentPhase =
    elapsed < 15 ? lines.gathering : elapsed < 45 ? lines.probing : lines.composing;
  const displayLine = currentPhase[lineIndex % currentPhase.length];

  // Phase label — what the system is "up to" right now.
  const phaseLabel =
    elapsed < 15 ? "Gathering" : elapsed < 45 ? "Probing" : "Composing";

  return (
    <main className="view thinking">
      <div className="thinking__stage">
        <p className="thinking__phase">{phaseLabel}</p>
        <p
          className="thinking__line"
          key={`${phaseLabel}-${lineIndex % currentPhase.length}`}
        >
          {displayLine}
        </p>
        <div className="thinking__meta">
          <span className="thinking__pulse" aria-hidden />
          <span className="thinking__elapsed">{fmtElapsed(elapsed)}</span>
        </div>
      </div>
    </main>
  );
}
