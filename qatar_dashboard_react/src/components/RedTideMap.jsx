import { useEffect, useMemo, useRef, useState } from "react";
import { gsap, ScrollTrigger, useGSAP, prefersReducedMotion } from "../animations/gsapSetup.js";
import { MONTH_NAMES, formatDay } from "../utils.js";

// Every check of the 2008 backtest as a map of the Gulf, one pixel per 4 km satellite square.
// The frames are a static file (public/data/redtide2008.json) fetched when the section gets
// close, so they don't weigh down the rest of the page.

const ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
const CHAR_VALUE = Object.fromEntries([...ALPHABET].map((c, i) => [c, i]));
const CLASS_COLORS = ["--map-land", "--map-sea", "--map-above", "--map-flagged"];
const SECONDS_PER_FRAME = 0.14;

const CHART_H = 150;
const CM = { top: 22, right: 8, bottom: 26, left: 58 };

function decode(cells, count) {
  const classes = new Uint8Array(count);
  for (let i = 0; i < cells.length; i++) {
    const n = CHAR_VALUE[cells[i]];
    const at = i * 3;
    if (at < count) classes[at] = n >> 4;
    if (at + 1 < count) classes[at + 1] = (n >> 2) & 3;
    if (at + 2 < count) classes[at + 2] = n & 3;
  }
  return classes;
}

function cssColor(name) {
  const hex = getComputedStyle(document.documentElement).getPropertyValue(name).trim().replace("#", "");
  return [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16));
}

function daysBetween(a, b) {
  return Math.round((new Date(b) - new Date(a)) / 86_400_000);
}

function relativeToSighting(date, sighting) {
  const d = daysBetween(sighting, date);
  if (d === 0) return "Around the day the bloom was first reported";
  if (d < 0) return `${-d} days before the bloom was first reported`;
  if (d <= 60) return `${d} days after it was first reported`;
  return `About ${Math.round(d / 30.4)} months after it was first reported`;
}

function roughly(km2) {
  if (km2 < 1000) return `${Math.round(km2 / 10) * 10}`;
  return `${Math.round(km2 / 1000).toLocaleString("en")},000`;
}

function describeFrame(frame) {
  if (frame.flagged_km2 === 0) return "Nothing flagged.";
  return (
    `Flagged: about ${roughly(frame.flagged_km2)} km². The nearest part was ` +
    `${Math.round(frame.km_to_origin)} km from Dibba and ${Math.round(frame.km_to_qatar)} km from Doha.`
  );
}

function captionFor(frame, data) {
  return `${relativeToSighting(frame.date, data.documented_first_sighting)}. ${describeFrame(frame)}`;
}

// Grid values are pixel centres; the image spans half a pixel beyond them on every side.
function placeOnMap(point, grid) {
  const latStep = (grid.north - grid.south) / (grid.rows - 1);
  const lonStep = (grid.east - grid.west) / (grid.cols - 1);
  return {
    left: `${((point.lon - (grid.west - lonStep / 2)) / (grid.cols * lonStep)) * 100}%`,
    top: `${((grid.north + latStep / 2 - point.lat) / (grid.rows * latStep)) * 100}%`,
  };
}

export default function RedTideMap({ theme }) {
  const rootRef = useRef(null);
  const canvasRef = useRef(null);
  const tweenRef = useRef(null);
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);
  const [frame, setFrame] = useState(null);
  const [playing, setPlaying] = useState(false);
  const [systemDark, setSystemDark] = useState(() => window.matchMedia("(prefers-color-scheme: dark)").matches);
  // The timeline is drawn at its real width, so its labels stay readable on a phone.
  const [chartW, setChartW] = useState(1000);

  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => setChartW(Math.max(300, Math.round(entry.contentRect.width))));
    observer.observe(rootRef.current);
    return () => observer.disconnect();
  }, []);

  // Load the frames once the section is within about a screen of the viewport.
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries[0].isIntersecting) return;
        observer.disconnect();
        fetch(`${import.meta.env.BASE_URL}data/redtide2008.json`)
          .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.statusText))))
          .then(setData)
          .catch(() => setFailed(true));
      },
      { rootMargin: "800px 0px" }
    );
    observer.observe(rootRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (e) => setSystemDark(e.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  const decoded = useMemo(() => {
    if (!data) return null;
    const count = data.grid.rows * data.grid.cols;
    return data.frames.map((f) => decode(f.cells, count));
  }, [data]);

  // The last check before the bloom was first reported: the frame the section is about.
  const keyFrame = useMemo(() => {
    if (!data) return 0;
    const before = data.frames.filter((f) => f.date < data.documented_first_sighting);
    return Math.max(0, before.length - 1);
  }, [data]);

  // Until the reader picks a date (or playback starts), show the key frame.
  const shown = data ? (frame ?? keyFrame) : null;

  // Draw the current frame. Redrawn when the theme changes, since the colours come from CSS.
  useEffect(() => {
    if (!decoded || shown === null) return;
    const { rows, cols } = data.grid;
    const ctx = canvasRef.current.getContext("2d");
    const image = ctx.createImageData(cols, rows);
    const colors = CLASS_COLORS.map(cssColor);
    const classes = decoded[shown];
    for (let i = 0; i < classes.length; i++) {
      const [r, g, b] = colors[classes[i]];
      image.data[i * 4] = r;
      image.data[i * 4 + 1] = g;
      image.data[i * 4 + 2] = b;
      image.data[i * 4 + 3] = 255;
    }
    ctx.putImageData(image, 0, 0);
  }, [decoded, data, shown, theme, systemDark]);

  function stop() {
    if (tweenRef.current) tweenRef.current.kill();
    tweenRef.current = null;
    setPlaying(false);
  }

  function playTo(from, to) {
    stop();
    const counter = { i: from };
    setFrame(from);
    setPlaying(true);
    tweenRef.current = gsap.to(counter, {
      i: to,
      duration: Math.max(0.3, (to - from) * SECONDS_PER_FRAME),
      ease: "none",
      onUpdate: () => setFrame(Math.round(counter.i)),
      onComplete: () => {
        tweenRef.current = null;
        setPlaying(false);
      },
    });
  }

  function togglePlay() {
    if (playing) return stop();
    const last = data.frames.length - 1;
    return playTo(shown >= last ? 0 : shown, last);
  }

  // First time the map scrolls into view: play the weeks up to the key frame, then stop there.
  useGSAP(
    () => {
      if (!data || prefersReducedMotion()) return;
      ScrollTrigger.create({
        trigger: rootRef.current,
        start: "top 65%",
        once: true,
        onEnter: () => playTo(0, keyFrame),
      });
      gsap.from(rootRef.current.querySelectorAll(".timeline-bar"), {
        scaleY: 0,
        transformOrigin: "50% 100%",
        duration: 0.6,
        ease: "power2.out",
        stagger: 0.004,
        scrollTrigger: { trigger: rootRef.current, start: "top 75%", once: true },
      });
    },
    { scope: rootRef, dependencies: [data, keyFrame] }
  );

  useEffect(() => () => tweenRef.current?.kill(), []);

  if (failed) return null;

  const grid = data?.grid;
  const midLat = grid ? (grid.north + grid.south) / 2 : 25.7;
  const aspect = grid ? (grid.cols * Math.cos((midLat * Math.PI) / 180)) / grid.rows : 2.07;
  const current = shown !== null ? data.frames[shown] : null;
  const longestNote = data
    ? data.frames.map((f) => captionFor(f, data)).reduce((a, b) => (b.length > a.length ? b : a), "")
    : " ";

  // Timeline: flagged area on each check. Linear scale; any non-zero day gets at least 2 px
  // so a small patch is still visible (the exact figure is in the caption above the map).
  const maxArea = data ? Math.max(...data.frames.map((f) => f.flagged_km2)) : 1;
  const plotW = chartW - CM.left - CM.right;
  const plotH = CHART_H - CM.top - CM.bottom;
  const band = data ? plotW / data.frames.length : 1;
  const yTop = Math.ceil(maxArea / 20000) * 20000;
  const yAt = (km2) => CM.top + plotH - (km2 / yTop) * plotH;
  const barHeight = (km2) => (km2 === 0 ? 0 : Math.max(2, (km2 / yTop) * plotH));
  const sightingIndex = data ? data.frames.findIndex((f) => f.date >= data.documented_first_sighting) : 0;
  // A label at the first check of every other month, skipping any that would run into the
  // previous one (roughly 7 px per character at this size).
  const monthTicks = [];
  if (data) {
    let lastRight = -Infinity;
    data.frames.forEach((f, i) => {
      const month = f.date.slice(5, 7);
      if (i > 0 && month === data.frames[i - 1].date.slice(5, 7)) return;
      if (Number(month) % 2 !== 0) return;
      const label = `${MONTH_NAMES[Number(month) - 1].slice(0, 3)}${i === 0 || month === "02" ? ` ${f.date.slice(0, 4)}` : ""}`;
      const x = CM.left + i * band;
      if (x < lastRight) return;
      monthTicks.push({ f, x, label });
      lastRight = x + label.length * 7 + 10;
    });
  }

  function frameFromPointer(evt) {
    const rect = evt.currentTarget.ownerSVGElement.getBoundingClientRect();
    const x = ((evt.clientX - rect.left) / rect.width) * chartW - CM.left;
    return Math.max(0, Math.min(data.frames.length - 1, Math.floor(x / band)));
  }

  return (
    <figure className="redtide-map" ref={rootRef}>
      {/* The hidden copy of the longest caption sits in the same grid cell as the real one, so the
          caption always takes the same height and the map doesn't jump as the text changes. */}
      <div className="map-caption">
        <div className="map-caption-sizer" aria-hidden="true">
          <div className="map-date">30 September 2008</div>
          <div className="map-note">{longestNote}</div>
        </div>
        <div aria-live={playing ? "off" : "polite"}>
          <div className="map-date">{current ? formatDay(current.date) : " "}</div>
          <div className="map-note">{current ? captionFor(current, data) : " "}</div>
        </div>
      </div>

      <div className="map-frame" style={{ aspectRatio: aspect }}>
        {grid && (
          <>
            <canvas
              ref={canvasRef}
              width={grid.cols}
              height={grid.rows}
              role="img"
              aria-label={current ? `Map of the Gulf on ${formatDay(current.date)}. ${describeFrame(current)}` : "Map of the Gulf"}
            />
            <span className="map-marker" style={placeOnMap(data.doha, grid)}>
              <span className="map-dot" />
              <span className="map-label">Doha</span>
            </span>
            <span className="map-marker" style={placeOnMap(data.origin, grid)}>
              <span className="map-dot" />
              <span className="map-label">
                Dibba<span className="label-extra">, where it was first seen</span>
              </span>
            </span>
          </>
        )}
      </div>

      <ul className="map-legend">
        <li>
          <span className="swatch" style={{ background: "var(--map-sea)" }} /> Normal for the month
        </li>
        <li>
          <span className="swatch" style={{ background: "var(--map-above)" }} /> Well above normal
        </li>
        <li>
          <span className="swatch" style={{ background: "var(--map-flagged)" }} /> Flagged by the check
        </li>
        <li>
          <span className="swatch" style={{ background: "var(--map-land)" }} /> Land
        </li>
      </ul>

      {data && (
        <div className="map-controls">
          <button className="play-button" onClick={togglePlay} aria-pressed={playing}>
            {playing ? "Pause" : shown === data.frames.length - 1 ? "Play again" : "Play the whole season"}
          </button>
          <label className="map-slider">
            <span className="visually-hidden">Date of the map</span>
            <input
              type="range"
              min={0}
              max={data.frames.length - 1}
              value={shown}
              aria-valuetext={current ? formatDay(current.date) : undefined}
              onChange={(e) => {
                stop();
                setFrame(Number(e.target.value));
              }}
            />
          </label>
        </div>
      )}

      {data && (
        <svg
          className="timeline"
          viewBox={`0 0 ${chartW} ${CHART_H}`}
          role="img"
          aria-label={`Flagged area on each check from August 2008 to May 2009, peaking at about ${roughly(maxArea)} km².`}
        >
          <text className="axis-text" x={CM.left - 8} y={12} textAnchor="end">
            km²
          </text>
          {[0, yTop / 2, yTop].map((v) => (
            <g key={v}>
              <line className="grid" x1={CM.left} x2={chartW - CM.right} y1={yAt(v)} y2={yAt(v)} />
              <text className="axis-text" x={CM.left - 8} y={yAt(v) + 4} textAnchor="end">
                {v.toLocaleString("en")}
              </text>
            </g>
          ))}
          {data.frames.map((f, i) => (
            <rect
              key={f.date}
              className={`timeline-bar${i === shown ? " is-current" : ""}`}
              x={CM.left + i * band + 0.5}
              width={Math.max(1, band - 1.5)}
              y={CM.top + plotH - barHeight(f.flagged_km2)}
              height={barHeight(f.flagged_km2)}
            />
          ))}
          {shown !== null && (
            <line
              className="timeline-cursor"
              x1={CM.left + (shown + 0.5) * band}
              x2={CM.left + (shown + 0.5) * band}
              y1={CM.top - 4}
              y2={CM.top + plotH}
            />
          )}
          <line
            className="timeline-marker"
            x1={CM.left + sightingIndex * band}
            x2={CM.left + sightingIndex * band}
            y1={CM.top - 14}
            y2={CM.top + plotH}
          />
          <text className="timeline-marker-label" x={CM.left + sightingIndex * band + 5} y={CM.top - 5}>
            First reported
          </text>
          {monthTicks.map(({ f, x, label }) => (
            <text key={f.date} className="axis-text" x={x} y={CHART_H - 6}>
              {label}
            </text>
          ))}
          <rect
            className="hit-area"
            x={CM.left}
            y={0}
            width={plotW}
            height={CHART_H - CM.bottom}
            onMouseMove={(evt) => {
              stop();
              setFrame(frameFromPointer(evt));
            }}
            onClick={(evt) => {
              stop();
              setFrame(frameFromPointer(evt));
            }}
          />
        </svg>
      )}
    </figure>
  );
}
