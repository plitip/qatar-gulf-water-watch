import Reveal from "../animations/Reveal.jsx";
import RedTideMap from "./RedTideMap.jsx";
import { MONTH_NAMES, formatDayShort } from "../utils.js";

// ["2008-08-01", "2008-08-19", "2008-08-22"] -> "1, 19 and 22 August 2008"
function listDays(isoDates) {
  const months = new Set(isoDates.map((d) => d.slice(0, 7)));
  const parts =
    months.size === 1 ? isoDates.map((d) => String(Number(d.slice(8, 10)))) : isoDates.map((d) => formatDayShort(d));
  const joined = parts.length === 1 ? parts[0] : `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
  const [year, month] = isoDates[0].split("-");
  return months.size === 1 ? `${joined} ${MONTH_NAMES[Number(month) - 1]} ${year}` : `${joined} ${year}`;
}

// What the backtest found before the bloom was reported, and how unusual that was compared
// with the same weeks of other years. Reported as found; the comparison is what makes it mean
// something, since a check that finds water near Dibba every August proves nothing.
function earlyFinding(bt) {
  const early = bt.flags_before_sighting;
  if (early.length === 0) {
    return "Applied to the archived images, the check didn't pick out anything before the bloom was first reported.";
  }
  const kms = early.map((f) => Math.round(f.km_to_origin));
  let text =
    `Applied to the archived images, the same check this site uses picked out unusual water ` +
    `${Math.min(...kms)} to ${Math.max(...kms)} km from where the bloom started, on ${listDays(early.map((f) => f.date))}, ` +
    "before it was first reported.";

  const comparison = bt.early_august_comparison;
  if (comparison) {
    const others = comparison.years.filter((y) => y.year !== 2008);
    const hits = others.filter((y) => y.checks_near_origin > 0);
    text +=
      hits.length === 0
        ? ` In the same weeks of ${others.length} other years, it found nothing like that.`
        : hits.length === 1
          ? ` In the same weeks of ${others.length} other years, it found anything like that only once, in ${hits[0].year}.`
          : ` In the same weeks of ${others.length} other years, it found anything like that in ${hits.length} of them.`;
    if (hits.length <= 2) {
      text += " So had it been running then, it would have pointed at the right stretch of sea days before the bloom was reported.";
    }
  }
  return text;
}

export default function RedTide2008({ backtest, theme }) {
  return (
    <Reveal as="section" className="section" aria-labelledby="red-tide-2008">
      <h2 id="red-tide-2008">The 2008 red tide</h2>
      <div className="prose">
        <p>
          In late August 2008, a bloom of the fish-killing alga <i>Cochlodinium polykrikoides</i> (now usually called{" "}
          <i>Margalefidinium polykrikoides</i>) was first seen near Dibba, on the UAE's east coast. Over the next nine
          months it spread through the Strait of Hormuz into the Gulf, reaching Qatari and Iranian waters, killing
          fish, damaging coral reefs and shutting desalination plants in the UAE and Oman for weeks.
        </p>
        {backtest && (
          <p>
            {earlyFinding(backtest)} Over the following months, the flagged water follows the bloom's documented path:
            through the Strait of Hormuz in October, then across the central Gulf northeast of Qatar by December.
          </p>
        )}
      </div>

      {backtest && <RedTideMap theme={theme} />}

      <p className="source">
        Source: Richlen et al.,{" "}
        <a
          href="https://www.sciencedirect.com/science/article/abs/pii/S1568988309001048"
          target="_blank"
          rel="noopener noreferrer"
        >
          The catastrophic 2008–2009 red tide in the Arabian gulf region
        </a>
        , <i>Harmful Algae</i>, 2010.
      </p>
    </Reveal>
  );
}
