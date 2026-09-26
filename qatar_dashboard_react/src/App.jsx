import { useEffect, useState } from "react";
import IntakeOverview from "./components/IntakeOverview.jsx";
import LatestCheck from "./components/LatestCheck.jsx";
import RedTide2008 from "./components/RedTide2008.jsx";
import StatusLine from "./components/StatusLine.jsx";
import ThemeToggle from "./components/ThemeToggle.jsx";
import Reveal from "./animations/Reveal.jsx";
import { CHL_HISTORY } from "./data/chlHistory.js";
import backtest2008 from "./data/backtest2008.json";
import gulfTrajectory from "./data/gulfTrajectory.json";
import status from "./data/status.json";

const SITES = ["Ras Laffan", "Ras Abu Fontas", "Umm Al Houl"];
const REPO_URL = "https://github.com/plitip/qatar-gulf-water-watch";

function storedTheme() {
  try {
    return localStorage.getItem("gww-theme") || "auto";
  } catch {
    return "auto"; // storage blocked (private browsing, strict settings)
  }
}

export default function App() {
  const [theme, setTheme] = useState(storedTheme);

  useEffect(() => {
    if (theme === "auto") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("gww-theme", theme);
    } catch {
      /* storage blocked: the choice just won't be remembered */
    }
  }, [theme]);

  function toggleTheme() {
    setTheme((prev) => {
      // auto -> the opposite of the system setting -> back to auto, so one click always flips the page
      const systemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      if (prev === "auto") return systemDark ? "light" : "dark";
      return "auto";
    });
  }

  return (
    <div className="page">
      <header className="masthead">
        <div>
          <h1>Gulf Water Watch</h1>
          <p className="intro">
            Satellite readings of chlorophyll at Qatar's three largest desalination intakes. Qatar gets almost all
            of its drinking water from desalination, and a large algal bloom can clog a plant's seawater intake.
          </p>
        </div>
        <ThemeToggle theme={theme} onToggle={toggleTheme} />
      </header>
      <StatusLine status={status} />

      <main>
        <IntakeOverview data={CHL_HISTORY} sites={SITES} />
        <LatestCheck status={status} trajectory={gulfTrajectory} />
        <RedTide2008 backtest={backtest2008} theme={theme} />

        <Reveal as="section" className="section" aria-labelledby="about-data">
          <h2 id="about-data">About the data</h2>
          <dl className="facts">
            <dt>Source</dt>
            <dd>
              Chlorophyll-a from the{" "}
              <a href="https://marine.copernicus.eu" target="_blank" rel="noopener noreferrer">
                Copernicus Marine Service
              </a>
              , combined from several ocean-colour satellites on a 4 km grid.
            </dd>
            <dt>At each intake</dt>
            <dd>The average of the two or three 4 km satellite squares nearest an estimated intake location.</dd>
            <dt>Usual range</dt>
            <dd>The average for that calendar month from 2018 to 2025, plus or minus two standard deviations.</dd>
            <dt>Wider Gulf</dt>
            <dd>
              A patch counts as unusual when at least four neighbouring 4 km squares are each above 3 mg/m³ and more
              than three standard deviations above their own normal for that month.
            </dd>
            <dt>Limits</dt>
            <dd>
              The intake locations are estimates, and the readings haven't been compared with water samples. Dust,
              sediment and a shallow seabed can all affect satellite colour readings near the coast.
            </dd>
          </dl>
        </Reveal>
      </main>

      <footer className="colophon">
        <a href={REPO_URL} target="_blank" rel="noopener noreferrer">
          Code and method on GitHub
        </a>
      </footer>
    </div>
  );
}
