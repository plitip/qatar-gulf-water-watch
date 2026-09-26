import { useEffect, useState } from "react";
import StatCards from "./components/StatCards.jsx";
import ChlorophyllChart from "./components/ChlorophyllChart.jsx";
import GulfPanel from "./components/GulfPanel.jsx";
import ThemeToggle from "./components/ThemeToggle.jsx";
import HistoryPanel from "./components/HistoryPanel.jsx";
import SplitText from "./animations/SplitText.jsx";
import Reveal from "./animations/Reveal.jsx";
import WaveLine from "./animations/WaveLine.jsx";
import { CHL_HISTORY } from "./data/chlHistory.js";
import gulfTrajectory from "./data/gulfTrajectory.json";

const SITES = ["Ras Laffan", "Ras Abu Fontas", "Umm Al Houl"];
const COLOR_VAR = {
  "Ras Laffan": "--series-1",
  "Ras Abu Fontas": "--series-2",
  "Umm Al Houl": "--series-3",
};

export default function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem("gww-theme") || "auto");

  useEffect(() => {
    if (theme === "auto") {
      document.documentElement.removeAttribute("data-theme");
    } else {
      document.documentElement.setAttribute("data-theme", theme);
    }
    try {
      localStorage.setItem("gww-theme", theme);
    } catch {
      /* ignore (private browsing, storage disabled, etc.) */
    }
  }, [theme]);

  function toggleTheme() {
    setTheme((prev) => {
      // cycles auto -> the opposite of system preference -> back to auto,
      // so one click always visibly flips the page regardless of OS setting
      const systemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      if (prev === "auto") return systemDark ? "light" : "dark";
      return "auto";
    });
  }

  return (
    <div className="wrap">
      <ThemeToggle theme={theme} onToggle={toggleTheme} />

      <header className="page-head">
        <Reveal as="span" className="eyebrow" y={8}>
          Qatar · Desalination Intake Monitoring
        </Reveal>
        <SplitText text="Gulf Water Watch" delay={0.1} />
        <WaveLine />
        <Reveal as="p" className="dek" y={12}>
          Satellite-derived chlorophyll-a near Qatar's three largest desalination intakes — Ras Laffan, Ras Abu
          Fontas, and Umm Al Houl — tracked monthly since 2018 for early signs of harmful algal blooms ("red tide")
          before they can clog intake filters.
        </Reveal>
      </header>

      <StatCards data={CHL_HISTORY} sites={SITES} colorVar={COLOR_VAR} />

      <Reveal>
        <ChlorophyllChart data={CHL_HISTORY} sites={SITES} colorVar={COLOR_VAR} />
      </Reveal>

      <Reveal>
        <GulfPanel trajectory={gulfTrajectory} />
      </Reveal>

      <Reveal>
        <HistoryPanel />
      </Reveal>

      <Reveal as="footer" className="notes" y={12}>
        <div>
          Data: Copernicus Marine Service ocean-colour chlorophyll-a (ESA Sentinel-3 / multi-sensor, 4km, gap-free
          reprocessed product), sampled in a ~5km box around each intake's approximate coordinates.
        </div>
        <div>
          Status pill compares the most recent reading against that site's own history for the{" "}
          <em>same calendar month</em> (mean ± 2 standard deviations of prior years' Augusts, Julys, etc.) — not a
          fixed threshold and not an all-months average — because chlorophyll here follows a strong seasonal cycle,
          and a global baseline would flag every normal warm season as "high."
        </div>
        <div>
          Gulf-wide trajectory: same-day statistical outliers (top 5% chlorophyll, above a 3.0 mg/m³ floor) scanned
          across the wider Strait of Hormuz–to–Qatar corridor, tracking the nearest one's distance to Qatar's coast
          day over day. A prototype signal, not a tracked/tagged patch of water — see{" "}
          <span className="mono">bloomwatch/gulf.py</span> for caveats.
        </div>
        <div>
          <strong>Prototype, not an operational warning system.</strong> Intake coordinates are approximate and
          unverified against the real facilities; thresholds are untuned against confirmed historical bloom events.
        </div>
      </Reveal>
    </div>
  );
}
