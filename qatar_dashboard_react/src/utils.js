export function mean(arr) {
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

export function stddev(arr, m) {
  const v = arr.reduce((a, b) => a + (b - m) * (b - m), 0) / arr.length;
  return Math.sqrt(v);
}

export const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

// "2026-08" -> "August 2026"
export function formatMonth(yyyyMm) {
  const [year, month] = yyyyMm.split("-").map(Number);
  return `${MONTH_NAMES[month - 1]} ${year}`;
}

// "2026-09-25" -> "25 September 2026"
export function formatDay(isoDate) {
  const [year, month, day] = isoDate.slice(0, 10).split("-").map(Number);
  return `${day} ${MONTH_NAMES[month - 1]} ${year}`;
}

// "2026-09-25" -> "25 September"
export function formatDayShort(isoDate) {
  const [, month, day] = isoDate.slice(0, 10).split("-").map(Number);
  return `${day} ${MONTH_NAMES[month - 1]}`;
}

// The latest monthly reading compared with the same calendar month in every earlier year.
// Chlorophyll here peaks every summer, so comparing August with other Augusts is the fair test.
export function latestVsSameMonth(series) {
  const readings = series.filter((r) => r.v !== null);
  const latest = readings[readings.length - 1];
  const past = readings
    .slice(0, -1)
    .filter((r) => r.month.slice(5) === latest.month.slice(5))
    .map((r) => r.v);
  const usual = mean(past);
  const sd = stddev(past, usual);
  return {
    latest,
    usual,
    low: Math.max(0, usual - 2 * sd),
    high: usual + 2 * sd,
    aboveRange: latest.v > usual + 2 * sd,
    belowRange: latest.v < usual - 2 * sd,
    highestOnRecord: latest.v > Math.max(...past),
    percentVsUsual: (latest.v / usual - 1) * 100,
    firstYear: readings[0].month.slice(0, 4),
    lastPastYear: String(Number(latest.month.slice(0, 4)) - 1),
  };
}

// "About 1.5 times a usual August (2.5)". A ratio, not a percentage, so a reader checking it
// with the rounded numbers on screen gets the same answer (3.7 / 2.5 is about 1.5).
export function comparedWithUsual(value, usual, monthName) {
  const ratio = value / usual;
  const usualText = `a usual ${monthName} (${usual.toFixed(1)})`;
  if (ratio >= 0.95 && ratio < 1.05) return `About the same as ${usualText}`;
  return `About ${ratio.toFixed(1)} times ${usualText}`;
}

// Months of `year`, before `beforeMonth`, whose reading was above its usual range.
export function monthsAboveRange(series, year, beforeMonth) {
  return seasonalProfile(series, year)
    .filter((p) => p.month < beforeMonth && p.value !== null && p.high !== null && p.value > p.high)
    .map((p) => p.month);
}

// [1, 2, 3, 4, 5, 6] -> "from January to June"; [1, 2, 4] -> "in January, February and April"
export function monthsPhrase(months) {
  const consecutive = months.every((m, i) => i === 0 || m === months[i - 1] + 1);
  if (months.length >= 3 && consecutive) {
    return `from ${MONTH_NAMES[months[0] - 1]} to ${MONTH_NAMES[months[months.length - 1] - 1]}`;
  }
  const names = months.map((m) => MONTH_NAMES[m - 1]);
  return `in ${names.length === 1 ? names[0] : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`}`;
}

const NUMBER_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"];
export function numberWord(n) {
  return NUMBER_WORDS[n] ?? String(n);
}

// Straight-line trend of the yearly average over full years, as % of the average per year.
export function yearlyTrendPercent(series, firstYear, lastYear) {
  const years = [];
  for (let y = firstYear; y <= lastYear; y++) {
    const values = series.filter((r) => r.v !== null && r.month.startsWith(`${y}-`)).map((r) => r.v);
    if (values.length === 12) years.push([y, mean(values)]);
  }
  const xs = years.map(([y]) => y);
  const ys = years.map(([, v]) => v);
  const mx = mean(xs);
  const my = mean(ys);
  const slope = xs.reduce((s, x, i) => s + (x - mx) * (ys[i] - my), 0) / xs.reduce((s, x) => s + (x - mx) ** 2, 0);
  return (slope / my) * 100;
}

// For each calendar month: the usual range from every year before `year`, and `year`'s reading.
export function seasonalProfile(series, year) {
  return MONTH_NAMES.map((_, i) => {
    const key = String(i + 1).padStart(2, "0");
    const past = series
      .filter((r) => r.v !== null && r.month.slice(5) === key && Number(r.month.slice(0, 4)) < year)
      .map((r) => r.v);
    const current = series.find((r) => r.month === `${year}-${key}`);
    if (past.length === 0) return { month: i + 1, low: null, high: null, value: current ? current.v : null };
    const usual = mean(past);
    const sd = stddev(past, usual);
    return {
      month: i + 1,
      usual,
      low: Math.max(0, usual - 2 * sd),
      high: usual + 2 * sd,
      value: current ? current.v : null,
    };
  });
}
