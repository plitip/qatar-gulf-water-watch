import IntakeOverview from "./components/IntakeOverview.jsx";
import LatestCheck from "./components/LatestCheck.jsx";
import RedTide2008 from "./components/RedTide2008.jsx";
import StatusLine from "./components/StatusLine.jsx";
import Reveal from "./animations/Reveal.jsx";
import { CHL_HISTORY } from "./data/chlHistory.js";
import backtest2008 from "./data/backtest2008.json";
import gulfTrajectory from "./data/gulfTrajectory.json";
import status from "./data/status.json";

const SITES = ["Ras Laffan", "Ras Abu Fontas", "Umm Al Houl"];
const REPO_URL = "https://github.com/plitip/qatar-gulf-water-watch";

// The dateline is the day of the latest check, like a newspaper's issue date.
function issueDate() {
  if (!status) return "";
  return new Date(status.last_run_utc).toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "Asia/Qatar",
  });
}

export default function App() {
  return (
    <div className="page">
      <header className="masthead">
        <p className="dateline">
          <span>Doha, Qatar</span>
          <span>{issueDate()}</span>
        </p>
        <div className="masthead-row">
          <span className="ear ear-left">Satellite edition</span>
          <h1>Gulf Water Watch</h1>
          <span className="ear ear-right">Updated daily</span>
        </div>
        <p className="intro">
          Satellite readings of chlorophyll at Qatar's three largest desalination intakes. Qatar gets almost all of
          its drinking water from desalination, and a large algal bloom can clog a plant's seawater intake.
        </p>
      </header>
      <StatusLine status={status} />

      <main>
        <IntakeOverview data={CHL_HISTORY} sites={SITES} />
        <LatestCheck status={status} trajectory={gulfTrajectory} />
        <RedTide2008 backtest={backtest2008} />

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
