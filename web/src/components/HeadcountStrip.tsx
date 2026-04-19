import type { HeadcountTrend } from "../types";
import "./HeadcountStrip.css";

interface Props {
  trends: HeadcountTrend[];
}

function fmtGrowth(pct: number | null | undefined): {
  label: string;
  tone: "up" | "down" | "flat";
} {
  if (pct === null || pct === undefined) return { label: "—", tone: "flat" };
  const abs = Math.abs(pct);
  if (abs < 5) return { label: "flat", tone: "flat" };
  // Show as "Nx" when multiplier is big; otherwise signed percent.
  const sign = pct > 0 ? "+" : "−";
  if (abs >= 100) {
    const multiplier = (pct / 100 + 1).toFixed(1).replace(/\.0$/, "");
    return { label: `${multiplier}×`, tone: pct > 0 ? "up" : "down" };
  }
  return {
    label: `${sign}${Math.round(abs)}%`,
    tone: pct > 0 ? "up" : "down",
  };
}

function fmtShare(pct: number | null | undefined): string | null {
  if (pct === null || pct === undefined) return null;
  if (pct < 0.5) return "<1% of team";
  return `${Math.round(pct)}% of team`;
}

export default function HeadcountStrip({ trends }: Props) {
  if (!trends || trends.length === 0) return null;

  return (
    <section className="sec hc-section">
      <p className="sec__head">Where they&rsquo;re growing</p>
      <ul className="hc-list">
        {trends.map((t) => {
          const growth = fmtGrowth(t.yoy_pct);
          const share = fmtShare(t.share_pct);
          return (
            <li key={t.function} className="hc-row">
              <span className="hc-row__name">{t.function}</span>
              <span className="hc-row__stats">
                {share && <span className="hc-row__share">{share}</span>}
                <span className={`hc-row__growth hc-row__growth--${growth.tone}`}>
                  {growth.label}
                  {t.yoy_pct !== null && t.yoy_pct !== undefined && growth.label !== "flat" && (
                    <span className="hc-row__growth-suffix"> YoY</span>
                  )}
                </span>
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
