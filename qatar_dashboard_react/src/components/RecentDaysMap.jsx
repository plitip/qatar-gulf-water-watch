import { useEffect, useMemo, useRef, useState } from "react";
import { gsap, ScrollTrigger, useGSAP, prefersReducedMotion } from "../animations/gsapSetup.js";
import { MONTH_NAMES, formatDay } from "../utils.js";
import { decode, drawClasses, mapAspect, placeOnMap, roughly } from "../maps/mapUtils.js";
import MapLegend from "../maps/MapLegend.jsx";

// The last few days with a satellite image, as maps of the Gulf, newest selected. Same map as
// the 2008 one; the daily run rewrites public/data/recent_days.json each morning.

const SECONDS_PER_DAY = 0.7;

function describeDay(frame) {
  if (frame.flagged_km2 === 0) return "Nothing flagged.";
  const where = frame.km_to_doha === null ? "" : ` The nearest part was ${frame.km_to_doha} km from Doha.`;
  return `Flagged: about ${roughly(frame.flagged_km2)} km².${where}`;
}

// "2026-09-19" -> ["19", "Sep"]
function dayParts(iso) {
  const [, month, day] = iso.split("-").map(Number);
  return [String(day), MONTH_NAMES[month - 1].slice(0, 3)];
}

export default function RecentDaysMap() {
  const rootRef = useRef(null);
  const canvasRef = useRef(null);
  const tweenRef = useRef(null);
  const [data, setData] = useState(null);
  const [picked, setPicked] = useState(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data/recent_days.json`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.statusText))))
      .then((d) => d.frames.length > 0 && setData(d))
      .catch(() => {});
  }, []);

  const decoded = useMemo(() => {
    if (!data) return null;
    const count = data.grid.rows * data.grid.cols;
    return data.frames.map((f) => decode(f.cells, count));
  }, [data]);

  const last = data ? data.frames.length - 1 : 0;
  const shown = picked ?? last;

  useEffect(() => {
    if (decoded) drawClasses(canvasRef.current, decoded[shown], data.grid.cols, data.grid.rows);
  }, [decoded, data, shown]);

  function stop() {
    tweenRef.current?.kill();
    tweenRef.current = null;
    setPlaying(false);
  }

  function playWeek() {
    stop();
    const counter = { i: 0 };
    setPicked(0);
    setPlaying(true);
    tweenRef.current = gsap.to(counter, {
      i: last,
      duration: last * SECONDS_PER_DAY,
      ease: `steps(${last})`,
      onUpdate: () => setPicked(Math.round(counter.i)),
      onComplete: () => {
        tweenRef.current = null;
        setPlaying(false);
      },
    });
  }

  // First time the map scrolls into view: run through the days, ending on the newest.
  useGSAP(
    () => {
      if (!data || last === 0 || prefersReducedMotion()) return;
      ScrollTrigger.create({ trigger: rootRef.current, start: "top 65%", once: true, onEnter: playWeek });
    },
    { scope: rootRef, dependencies: [data] }
  );

  useEffect(() => () => tweenRef.current?.kill(), []);

  if (!data) return null;

  const current = data.frames[shown];
  const maxArea = Math.max(1, ...data.frames.map((f) => f.flagged_km2));
  const first = data.frames[0].date;
  const spanDays = Math.round((new Date(data.frames[last].date) - new Date(first)) / 86_400_000) + 1;

  return (
    <figure className="recent-map" ref={rootRef}>
      <h3 className="recent-map-title">The last {data.frames.length} days on the map</h3>
      <div aria-live={playing ? "off" : "polite"} className="recent-map-caption">
        <div className="map-date">{formatDay(current.date)}</div>
        <div className="map-note">{describeDay(current)}</div>
      </div>

      <div className="map-frame" style={{ aspectRatio: mapAspect(data.grid) }}>
        <canvas
          ref={canvasRef}
          width={data.grid.cols}
          height={data.grid.rows}
          role="img"
          aria-label={`Map of the Gulf on ${formatDay(current.date)}. ${describeDay(current)}`}
        />
        <span className="map-marker" style={placeOnMap(data.doha, data.grid)}>
          <span className="map-dot" />
          <span className="map-label">Doha</span>
        </span>
      </div>

      <MapLegend />

      <div className="day-strip" role="group" aria-label="Pick a day">
        {data.frames.map((f, i) => {
          const [day, month] = dayParts(f.date);
          return (
            <button
              key={f.date}
              type="button"
              className={`day-button${i === shown ? " is-current" : ""}`}
              aria-pressed={i === shown}
              aria-label={`${formatDay(f.date)}. ${describeDay(f)}`}
              onClick={() => {
                stop();
                setPicked(i);
              }}
            >
              <span className="day-bar" aria-hidden="true">
                <span style={{ height: f.flagged_km2 === 0 ? 0 : `${Math.max(8, (f.flagged_km2 / maxArea) * 100)}%` }} />
              </span>
              <span className="day-num">{day}</span>
              <span className="day-month">{month}</span>
            </button>
          );
        })}
      </div>

      {last > 0 && (
        <div className="map-controls">
          <button className="play-button" onClick={playing ? stop : playWeek} aria-pressed={playing}>
            {playing ? "Pause" : "Play these days"}
          </button>
          <span className="recent-map-note">
            Bars show the flagged area each day.
            {spanDays > data.frames.length && " Days with no satellite image are left out."}
          </span>
        </div>
      )}
    </figure>
  );
}
