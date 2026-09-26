import { useRef, useState } from "react";

const W = 900,
  H = 220,
  M = { top: 14, right: 16, bottom: 26, left: 42 };
const PLOT_W = W - M.left - M.right,
  PLOT_H = H - M.top - M.bottom;

const VERDICT_META = {
  approaching: { cls: "warn", label: "Approaching" },
  receding: { cls: "good", label: "Receding" },
  no_clear_trend: { cls: "neutral", label: "No clear trend" },
  insufficient_data: { cls: "neutral", label: "Insufficient data" },
};

export default function GulfPanel({ trajectory }) {
  const svgRef = useRef(null);
  const [hoverIdx, setHoverIdx] = useState(null);

  if (!trajectory) {
    return (
      <section className="panel" id="gulfPanel">
        <div className="panel-head">
          <div>
            <div className="panel-title">Gulf-wide bloom trajectory</div>
            <div className="panel-sub">Strait of Hormuz → Qatar corridor, daily hotspot scan</div>
          </div>
        </div>
        <p className="stat-note" style={{ padding: "8px 4px 14px", fontSize: 12.5, lineHeight: 1.6 }}>
          No trajectory data published yet. The wider-Gulf scan (<span className="mono">bloomwatch/gulf.py</span>)
          runs on live satellite data, but its hotspot rule keeps flagging the permanently murky water off Doha, so
          the trend it produces doesn't mean much yet. This panel stays empty until that's fixed.
        </p>
      </section>
    );
  }

  const { window_end_date, window_days, daily, trend } = trajectory;
  const verdict = VERDICT_META[trend.verdict] || { cls: "neutral", label: trend.verdict };

  let lastReading = null;
  for (let i = daily.length - 1; i >= 0; i--) {
    if (daily[i].nearest_km !== null) {
      lastReading = daily[i];
      break;
    }
  }

  const readings = daily.map((d) => d.nearest_km).filter((v) => v !== null);
  const yMax = readings.length ? Math.ceil(Math.max(...readings) * 1.15) : 100;
  const yMin = 0;

  const gx = (i) => M.left + (daily.length === 1 ? 0 : (i / (daily.length - 1)) * PLOT_W);
  const gy = (v) => M.top + PLOT_H - ((v - yMin) / (yMax - yMin)) * PLOT_H;

  // build path, breaking on gap days (null readings)
  let path = "";
  daily.forEach((d, i) => {
    if (d.nearest_km === null) {
      path += " ";
      return;
    }
    path += (path === "" || path.slice(-1) === " " ? "M" : "L") + gx(i) + "," + gy(d.nearest_km) + " ";
  });

  const ySteps = 4;
  const yTicks = Array.from({ length: ySteps + 1 }, (_, s) => yMin + (s / ySteps) * (yMax - yMin));

  function handleMove(evt) {
    const rect = svgRef.current.getBoundingClientRect();
    const relX = ((evt.clientX - rect.left) / rect.width) * W;
    let i = Math.round(((relX - M.left) / PLOT_W) * (daily.length - 1));
    i = Math.max(0, Math.min(daily.length - 1, i));
    setHoverIdx(i);
  }

  const hoverDay = hoverIdx !== null ? daily[hoverIdx] : null;

  return (
    <section className="panel" id="gulfPanel">
      <div className="panel-head">
        <div>
          <div className="panel-title">Gulf-wide bloom trajectory</div>
          <div className="panel-sub">
            Window ending {window_end_date} · {window_days}-day scan, Strait of Hormuz to Qatar's coast
          </div>
        </div>
      </div>

      <div className="stat-row two-up">
        <div className="stat-card">
          <div className="stat-top">
            <span className="stat-name">Nearest hotspot</span>
          </div>
          <div className="stat-value tabular">
            {lastReading ? lastReading.nearest_km.toFixed(0) : "—"}
            <span className="stat-unit"> km from coast</span>
          </div>
          <span className="stat-note">
            {lastReading ? `${lastReading.date} · ${lastReading.hotspot_count} elevated pixel(s)` : "no usable reading in window"}
          </span>
        </div>
        <div className="stat-card">
          <div className="stat-top">
            <span className="stat-name">Trend</span>
            <span className={`pill ${verdict.cls}`}>{verdict.label}</span>
          </div>
          <div className="stat-note" style={{ marginTop: 2 }}>
            {trend.message}
          </div>
        </div>
      </div>

      <div className="chart-wrap" style={{ marginTop: 12 }}>
        <div className="chart-scroll">
          <svg
            className="chart"
            ref={svgRef}
            viewBox={`0 0 ${W} ${H}`}
            preserveAspectRatio="xMidYMid meet"
            onMouseMove={handleMove}
            onMouseLeave={() => setHoverIdx(null)}
          >
            {yTicks.map((v, s) => {
              const y = gy(v);
              return (
                <g key={s}>
                  <line className="grid-line" x1={M.left} x2={W - M.right} y1={y} y2={y} />
                  <text className="axis-label" x={M.left - 8} y={y + 3} textAnchor="end">
                    {Math.round(v)}
                  </text>
                </g>
              );
            })}
            {daily.map((d, i) => (
              <text key={i} className="axis-label" x={gx(i)} y={H - 8} textAnchor="middle">
                {d.date.slice(5)}
              </text>
            ))}
            <line className="axis-line" x1={M.left} x2={W - M.right} y1={M.top + PLOT_H} y2={M.top + PLOT_H} />
            <path className="series-line" d={path} stroke="var(--series-1)" />
            {daily.map(
              (d, i) =>
                d.nearest_km !== null && (
                  <circle key={i} cx={gx(i)} cy={gy(d.nearest_km)} r={hoverIdx === i ? 5 : 3} fill="var(--series-1)" />
                )
            )}
            {hoverIdx !== null && (
              <line className="hover-crosshair" x1={gx(hoverIdx)} x2={gx(hoverIdx)} y1={M.top} y2={M.top + PLOT_H} />
            )}
          </svg>
        </div>
        {hoverDay && (
          <div className="tooltip visible" style={{ left: 12, top: 4 }}>
            <div className="tooltip-month">{hoverDay.date}</div>
            <div className="tooltip-row">
              <span className="tooltip-name">
                <span className="tooltip-swatch" style={{ background: "var(--series-1)" }} />
                Nearest hotspot
              </span>
              <span className="tooltip-val">
                {hoverDay.nearest_km === null ? "no data" : `${hoverDay.nearest_km.toFixed(0)} km`}
              </span>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
