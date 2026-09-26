import CountUp from "../animations/CountUp.jsx";
import Reveal from "../animations/Reveal.jsx";
import MonthlyTable from "./MonthlyTable.jsx";
import SeasonalChart from "./SeasonalChart.jsx";
import {
  MONTH_NAMES,
  comparedWithUsual,
  formatMonth,
  latestVsSameMonth,
  monthsAboveRange,
  monthsPhrase,
  numberWord,
  seasonalProfile,
  yearlyTrendPercent,
} from "../utils.js";

const TREND_WORTH_MENTIONING = 2; // % a year

function headlineFor(stats, monthLabel, monthName, yearsOfData) {
  const all = (key) => stats.every((s) => s[key]);
  const count = (key) => stats.filter((s) => s[key]).length;
  if (all("highestOnRecord")) {
    return `In ${monthLabel}, all three intakes had their highest ${monthName} reading in the ${numberWord(yearsOfData)} years of data.`;
  }
  if (all("aboveRange")) return `In ${monthLabel}, all three intakes were above their usual ${monthName} range.`;
  if (count("aboveRange") > 0) {
    return `In ${monthLabel}, ${count("aboveRange")} of the three intakes were above their usual ${monthName} range.`;
  }
  if (count("belowRange") > 0) {
    return `In ${monthLabel}, ${count("belowRange")} of the three intakes were below their usual ${monthName} range.`;
  }
  return `In ${monthLabel}, all three intakes were within their usual ${monthName} range.`;
}

// Which intakes were also above their range earlier this year, as one sentence.
function earlierMonthsSentence(earlier, monthName) {
  if (earlier.length === 0) return `Before ${monthName}, all three were within their usual ranges this year.`;
  // The intake with the most months above its range leads, since it's the bigger story.
  const sorted = [...earlier].sort((a, b) => b.months.length - a.months.length);
  const parts = sorted.map((e, i) =>
    i === 0 ? `${e.site} was also above its usual range ${monthsPhrase(e.months)}` : `${e.site} ${monthsPhrase(e.months)}`
  );
  return `${parts.length === 1 ? parts[0] : `${parts.slice(0, -1).join(", ")}, and ${parts[parts.length - 1]}`}.`;
}

// Leaves room above the highest line so its label doesn't touch the top of the chart.
function niceScale(maxValue) {
  const step = maxValue > 10 ? 4 : 2;
  const top = Math.ceil(maxValue * 1.12);
  return { yMax: top, yTicks: Array.from({ length: Math.floor(top / step) + 1 }, (_, i) => i * step) };
}

export default function IntakeOverview({ data, sites }) {
  const stats = sites.map((site) => ({ site, ...latestVsSameMonth(data[site]) }));
  const latestMonth = stats[0].latest.month;
  const year = Number(latestMonth.slice(0, 4));
  const monthNumber = Number(latestMonth.slice(5));
  const monthName = MONTH_NAMES[monthNumber - 1];
  const { firstYear, lastPastYear } = stats[0];
  const yearsOfData = year - Number(firstYear) + 1;

  const profiles = Object.fromEntries(sites.map((site) => [site, seasonalProfile(data[site], year)]));
  const chartValues = Object.values(profiles).flatMap((p) => p.flatMap((m) => [m.high, m.value]));
  const { yMax, yTicks } = niceScale(Math.max(...chartValues.filter((v) => v !== null)));

  const earlier = sites
    .map((site) => ({ site, months: monthsAboveRange(data[site], year, monthNumber) }))
    .filter((e) => e.months.length > 0);
  const trends = Object.fromEntries(
    sites.map((site) => [site, yearlyTrendPercent(data[site], Number(firstYear), Number(lastPastYear))])
  );

  return (
    <section className="overview" aria-labelledby="overview-headline">
      <Reveal>
        <h2 id="overview-headline" className="headline">
          {headlineFor(stats, formatMonth(latestMonth), monthName, yearsOfData)}
        </h2>
        <p className="headline-note">
          {earlierMonthsSentence(earlier, monthName)} As of August 2026 the open water of the central Gulf wasn't
          unusually green, so the rise looks local to the coast. More chlorophyll usually means more algae, but near the
          shore sediment can look the same to a satellite, and on its own it doesn't mean a harmful bloom.
        </p>
      </Reveal>

      <Reveal className="intakes" stagger={0.12}>
        {stats.map((stat) => {
          const trend = trends[stat.site];
          return (
            <div className="intake" key={stat.site}>
              <h3>{stat.site}</h3>
              <p className="figure">
                <CountUp value={stat.latest.v} decimals={1} className="figure-value" />
                <span className="figure-unit">mg/m³</span>
              </p>
              <p className="figure-context">
                {comparedWithUsual(stat.latest.v, stat.usual, monthName)}
                <br />
                Usual range {stat.low.toFixed(1)} to {stat.high.toFixed(1)}
                {Math.abs(trend) >= TREND_WORTH_MENTIONING && (
                  <>
                    <br />
                    {trend > 0 ? "Rising" : "Falling"} about {Math.round(Math.abs(trend))}% a year since {firstYear}
                  </>
                )}
              </p>
              <SeasonalChart site={stat.site} profile={profiles[stat.site]} year={year} yMax={yMax} yTicks={yTicks} />
            </div>
          );
        })}
      </Reveal>

      <p className="chart-key">
        <span className="key-line" aria-hidden="true" /> {year}, monthly average
        <span className="key-band" aria-hidden="true" /> Usual range, {firstYear}–{lastPastYear}
      </p>

      <MonthlyTable data={data} sites={sites} />
    </section>
  );
}
