import { useRef, useState } from "react";
import { gsap, useGSAP, prefersReducedMotion } from "../animations/gsapSetup.js";
import { MONTH_NAMES } from "../utils.js";

const W = 320;
const H = 200;
const M = { top: 24, right: 36, bottom: 26, left: 30 };
const PLOT_W = W - M.left - M.right;
const PLOT_H = H - M.top - M.bottom;
const X_TICK_MONTHS = [1, 4, 7, 10];

// One intake: this year's monthly readings (line) over the usual range for each month
// (shaded band: the average of earlier years, plus or minus 2 standard deviations).
export default function SeasonalChart({ site, profile, year, yMax, yTicks }) {
  const figureRef = useRef(null);
  const [active, setActive] = useState(null);

  const x = (i) => M.left + (i / 11) * PLOT_W;
  const y = (v) => M.top + PLOT_H - (v / yMax) * PLOT_H;

  const banded = profile.map((p, i) => ({ ...p, i })).filter((p) => p.low !== null);
  const bandPath = banded.length
    ? `M${banded.map((p) => `${x(p.i)},${y(p.high)}`).join(" L")} L${[...banded]
        .reverse()
        .map((p) => `${x(p.i)},${y(p.low)}`)
        .join(" L")} Z`
    : "";
  const measured = profile.map((p, i) => ({ ...p, i })).filter((p) => p.value !== null);
  const linePath = measured.map((p, k) => `${k === 0 ? "M" : "L"}${x(p.i)},${y(p.value)}`).join(" ");
  const last = measured[measured.length - 1];

  useGSAP(
    () => {
      if (prefersReducedMotion()) return;
      const line = figureRef.current.querySelector(".this-year");
      const length = line.getTotalLength();
      gsap.set(line, { strokeDasharray: length, strokeDashoffset: length });
      gsap.to(line, {
        strokeDashoffset: 0,
        duration: 1.6,
        ease: "power2.inOut",
        clearProps: "strokeDasharray,strokeDashoffset",
        scrollTrigger: { trigger: figureRef.current, start: "top 85%", once: true },
      });
    },
    { scope: figureRef }
  );

  function monthFromPointer(evt) {
    const rect = evt.currentTarget.ownerSVGElement.getBoundingClientRect();
    const svgX = ((evt.clientX - rect.left) / rect.width) * W;
    return Math.max(0, Math.min(11, Math.round(((svgX - M.left) / PLOT_W) * 11)));
  }

  function onKeyDown(evt) {
    if (evt.key === "ArrowRight") setActive((i) => Math.min(11, (i ?? last.i) + 1));
    if (evt.key === "ArrowLeft") setActive((i) => Math.max(0, (i ?? last.i) - 1));
  }

  const point = active === null ? null : profile[active];
  const tipAlign = active === null ? "" : active <= 2 ? "left" : active >= 9 ? "right" : "center";
  const describe =
    `${site}: monthly chlorophyll in ${year} against the usual range for each month. ` +
    `${MONTH_NAMES[last.i]} ${year} was ${last.value.toFixed(1)} mg/m³; ` +
    `the usual ${MONTH_NAMES[last.i]} range is ${last.low.toFixed(1)} to ${last.high.toFixed(1)}.`;

  return (
    <figure className="seasonal" ref={figureRef}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={describe}>
        <text className="axis-text" x={M.left - 6} y={12} textAnchor="end">
          mg/m³
        </text>
        {yTicks.map((v) => (
          <g key={v}>
            <line className="grid" x1={M.left} x2={W - M.right} y1={y(v)} y2={y(v)} />
            <text className="axis-text" x={M.left - 6} y={y(v) + 4} textAnchor="end">
              {v}
            </text>
          </g>
        ))}
        {X_TICK_MONTHS.map((m) => (
          <text key={m} className="axis-text" x={x(m - 1)} y={H - 6} textAnchor="middle">
            {MONTH_NAMES[m - 1].slice(0, 3)}
          </text>
        ))}

        <path className="band" d={bandPath} />
        <path className="this-year" d={linePath} />

        {point && <line className="crosshair" x1={x(active)} x2={x(active)} y1={M.top} y2={M.top + PLOT_H} />}
        {point && point.value !== null && active !== last.i && (
          <circle className="dot" cx={x(active)} cy={y(point.value)} r={4} />
        )}

        <circle className="dot" cx={x(last.i)} cy={y(last.value)} r={4.5} />
        <text className="end-label" x={x(last.i) + 9} y={y(last.value) + 4}>
          {last.value.toFixed(1)}
        </text>

        <rect
          className="hit-area"
          x={M.left - 10}
          y={M.top}
          width={PLOT_W + 20}
          height={PLOT_H}
          tabIndex={0}
          aria-label={`${site}: use the left and right arrow keys to read each month`}
          onMouseMove={(evt) => setActive(monthFromPointer(evt))}
          onMouseLeave={() => setActive(null)}
          onFocus={() => setActive(last.i)}
          onBlur={() => setActive(null)}
          onKeyDown={onKeyDown}
        />
      </svg>

      {point && (
        <div className={`tip tip-${tipAlign}`} style={{ left: `${(x(active) / W) * 100}%` }} aria-hidden="true">
          <div className="tip-title">
            {MONTH_NAMES[active]} {year}
          </div>
          <div>{point.value === null ? "No reading" : `${point.value.toFixed(1)} mg/m³`}</div>
          {point.low !== null && (
            <div className="tip-muted">
              Usual range: {point.low.toFixed(1)} to {point.high.toFixed(1)}
            </div>
          )}
        </div>
      )}
    </figure>
  );
}
