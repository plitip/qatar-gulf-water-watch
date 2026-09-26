import { useRef, useState } from "react";
import { gsap, useGSAP, prefersReducedMotion } from "../animations/gsapSetup.js";

const W = 900,
  H = 320,
  M = { top: 14, right: 16, bottom: 28, left: 42 };
const PLOT_W = W - M.left - M.right,
  PLOT_H = H - M.top - M.bottom;

export default function ChlorophyllChart({ data, sites, colorVar }) {
  const svgRef = useRef(null);
  const [hoverIdx, setHoverIdx] = useState(null);
  const [tooltipPos, setTooltipPos] = useState({ left: 0, top: 0 });
  const [hiddenSites, setHiddenSites] = useState(() => new Set());
  const [showTable, setShowTable] = useState(false);
  const panelRef = useRef(null);

  // Draw each site's line from left to right the first time the chart scrolls
  // into view. Uses the classic stroke-dash trick: dash length = path length,
  // then slide the dash offset to 0. clearProps removes the dash afterwards so
  // the finished line is a normal solid stroke.
  useGSAP(
    () => {
      if (prefersReducedMotion()) return;
      const lines = panelRef.current.querySelectorAll(".series-line");
      lines.forEach((line) => {
        const len = line.getTotalLength();
        gsap.set(line, { strokeDasharray: len, strokeDashoffset: len });
      });
      gsap.to(lines, {
        strokeDashoffset: 0,
        duration: 2.2,
        ease: "power2.inOut",
        stagger: 0.25,
        clearProps: "strokeDasharray,strokeDashoffset",
        scrollTrigger: { trigger: panelRef.current, start: "top 80%", once: true },
      });
    },
    { scope: panelRef }
  );

  const months = data[sites[0]].map((d) => d.month);
  const allValues = sites.flatMap((s) => data[s].map((d) => d.v).filter((v) => v !== null));
  const yMax = Math.ceil((Math.max(...allValues) * 1.1 * 10)) / 10;
  const yMin = 0;

  const xPos = (i) => M.left + (i / (months.length - 1)) * PLOT_W;
  const yPos = (v) => M.top + PLOT_H - ((v - yMin) / (yMax - yMin)) * PLOT_H;

  const ySteps = 4;
  const yTicks = Array.from({ length: ySteps + 1 }, (_, s) => yMin + (s / ySteps) * (yMax - yMin));
  const xTicks = months
    .map((m, i) => ({ m, i }))
    .filter(({ m }) => m.slice(5) === "01");

  // ~100 points x 3 sites: cheap enough to rebuild on every render, so no memo
  // (and no dependency list to keep in sync with xPos/yPos).
  const paths = sites.map((site) => {
    let d = "";
    data[site].forEach((p, i) => {
      if (p.v === null) return;
      d += (d === "" ? "M" : "L") + xPos(i) + "," + yPos(p.v) + " ";
    });
    return { site, d };
  });

  function handleMove(evt) {
    const rect = svgRef.current.getBoundingClientRect();
    const relX = ((evt.clientX - rect.left) / rect.width) * W;
    let i = Math.round(((relX - M.left) / PLOT_W) * (months.length - 1));
    i = Math.max(0, Math.min(months.length - 1, i));
    setHoverIdx(i);

    const wrapRect = svgRef.current.parentElement.getBoundingClientRect();
    const x = xPos(i);
    const left = (x / W) * wrapRect.width;
    setTooltipPos({ left: Math.min(left + 14, wrapRect.width - 160), top: 0 });
  }

  function toggleSite(site) {
    setHiddenSites((prev) => {
      const next = new Set(prev);
      if (next.has(site)) next.delete(site);
      else next.add(site);
      return next;
    });
  }

  return (
    <section className="panel" ref={panelRef}>
      <div className="panel-head">
        <div>
          <div className="panel-title">Chlorophyll-a, monthly average</div>
          <div className="panel-sub">2018–2026 · Copernicus Marine reprocessed ocean-colour archive</div>
        </div>
        <button className="table-toggle" onClick={() => setShowTable((v) => !v)}>
          {showTable ? "Hide table" : "Show as table"}
        </button>
      </div>

      <div className="legend">
        {sites.map((site) => (
          <button
            key={site}
            className={`legend-item ${hiddenSites.has(site) ? "dimmed" : ""}`}
            onClick={() => toggleSite(site)}
            title="Click to toggle this series"
          >
            <span className="legend-swatch" style={{ background: `var(${colorVar[site]})` }} />
            {site}
          </button>
        ))}
      </div>

      <div className="chart-wrap">
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
              const y = yPos(v);
              return (
                <g key={s}>
                  <line className="grid-line" x1={M.left} x2={W - M.right} y1={y} y2={y} />
                  <text className="axis-label" x={M.left - 8} y={y + 3} textAnchor="end">
                    {v.toFixed(1)}
                  </text>
                </g>
              );
            })}

            {xTicks.map(({ m, i }) => {
              const x = xPos(i);
              return (
                <g key={i}>
                  <line className="grid-line" x1={x} x2={x} y1={M.top} y2={M.top + PLOT_H} />
                  <text className="axis-label" x={x} y={H - 10} textAnchor="middle">
                    {m.slice(0, 4)}
                  </text>
                </g>
              );
            })}

            <line className="axis-line" x1={M.left} x2={W - M.right} y1={M.top + PLOT_H} y2={M.top + PLOT_H} />

            {paths.map(({ site, d }) => (
              <path
                key={site}
                className="series-line"
                d={d}
                stroke={`var(${colorVar[site]})`}
                style={{ opacity: hiddenSites.has(site) ? 0.08 : 1 }}
              />
            ))}

            {hoverIdx !== null && (
              <line
                className="hover-crosshair"
                x1={xPos(hoverIdx)}
                x2={xPos(hoverIdx)}
                y1={M.top}
                y2={M.top + PLOT_H}
              />
            )}
            {hoverIdx !== null &&
              sites.map((site) => {
                if (hiddenSites.has(site)) return null;
                const p = data[site][hoverIdx];
                if (p.v === null) return null;
                return (
                  <circle
                    key={site}
                    cx={xPos(hoverIdx)}
                    cy={yPos(p.v)}
                    r={4}
                    fill={`var(${colorVar[site]})`}
                    stroke="var(--surface-1)"
                    strokeWidth={2}
                  />
                );
              })}
          </svg>
        </div>

        <div
          className={`tooltip ${hoverIdx !== null ? "visible" : ""}`}
          style={{ left: tooltipPos.left, top: 4 }}
        >
          {hoverIdx !== null && (
            <>
              <div className="tooltip-month">{months[hoverIdx]}</div>
              {sites.map((site) => {
                const p = data[site][hoverIdx];
                return (
                  <div className="tooltip-row" key={site}>
                    <span className="tooltip-name">
                      <span className="tooltip-swatch" style={{ background: `var(${colorVar[site]})` }} />
                      {site}
                    </span>
                    <span className="tooltip-val">{p.v === null ? "—" : p.v.toFixed(2)}</span>
                  </div>
                );
              })}
            </>
          )}
        </div>
      </div>

      {showTable && (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Month</th>
                {sites.map((s) => (
                  <th key={s}>{s}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {months.map((m, i) => (
                <tr key={m}>
                  <td>{m}</td>
                  {sites.map((s) => {
                    const v = data[s][i].v;
                    return <td key={s}>{v === null ? "—" : v.toFixed(2)}</td>;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
