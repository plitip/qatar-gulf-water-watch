import { mean, stddev } from "../utils.js";
import Reveal from "../animations/Reveal.jsx";
import CountUp from "../animations/CountUp.jsx";

const CheckIcon = () => (
  <svg viewBox="0 0 20 20" fill="currentColor">
    <path d="M8 13.4 4.6 10l-1.4 1.4L8 16.2l9-9L15.6 5.8z" />
  </svg>
);
const WarnIcon = () => (
  <svg viewBox="0 0 20 20" fill="currentColor">
    <path d="M10 2 1 18h18L10 2zm0 5a1 1 0 011 1v4a1 1 0 01-2 0V8a1 1 0 011-1zm0 8a1.2 1.2 0 110 2.4 1.2 1.2 0 010-2.4z" />
  </svg>
);

export default function StatCards({ data, sites, colorVar }) {
  return (
    <Reveal className="stat-row" id="statRow" stagger={0.12}>
      {sites.map((site) => {
        const series = data[site].filter((d) => d.v !== null);
        const latest = series[series.length - 1];
        const latestMonthNum = latest.month.slice(5, 7);

        const sameMonthHistory = series
          .slice(0, -1)
          .filter((d) => d.month.slice(5, 7) === latestMonthNum)
          .map((d) => d.v);

        const m = mean(sameMonthHistory);
        const sd = stddev(sameMonthHistory, m);
        const isHigh = latest.v > m + 2 * sd;
        const monthName = new Date(latest.month + "-01").toLocaleString("en", { month: "long" });

        return (
          <div className="stat-card" key={site}>
            <div className="stat-top">
              <span className="stat-name">{site}</span>
              <span className="stat-dot" style={{ background: `var(${colorVar[site]})` }} />
            </div>
            <div className="stat-value tabular">
              <CountUp value={latest.v} decimals={2} />
              <span className="stat-unit"> mg/m³</span>
            </div>
            <span className={`pill ${isHigh ? "warn" : "good"}`}>
              {isHigh ? <WarnIcon /> : <CheckIcon />}
              {isHigh ? `Above normal for ${monthName}` : `Normal for ${monthName}`}
            </span>
            <span className="stat-note">
              {latest.month} · vs {sameMonthHistory.length} past {monthName}s, mean {m.toFixed(2)} ± {sd.toFixed(2)}
            </span>
          </div>
        );
      })}
    </Reveal>
  );
}
