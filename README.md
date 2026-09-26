# Gulf Water Watch

Satellite monitoring of chlorophyll-a near Qatar's three largest desalination intakes
(Ras Laffan, Ras Abu Fontas, Umm Al Houl), as an early-warning prototype for harmful
algal blooms ("red tide").

Qatar gets almost all of its drinking water from desalination. In 2008–09 a bloom of
*Cochlodinium polykrikoides* spread from the Gulf of Oman into the Arabian Gulf, reached
Qatari waters, and forced desalination plants in the UAE and Oman offline for weeks. A
bloom that clogs intake filters is a water-supply problem, and satellites can see
chlorophyll build up days before it reaches the coast.

![React dashboard, dark mode](docs/screenshots/react_dashboard_dark.png)

## What it does

- **Intake check (daily).** Downloads the latest Copernicus Marine chlorophyll scene,
  averages a ~5 km box at each intake, and flags a reading more than 2 standard
  deviations above that intake's own history.
- **Seasonal baseline.** Chlorophyll here peaks every warm season, so the dashboard
  compares each month against the *same calendar month* in previous years, not against
  a year-round average that would flag every normal summer.
- **Wider-Gulf scan.** Looks for chlorophyll hotspots between the Strait of Hormuz and
  Qatar and tracks whether the nearest one is closing in over ten days.
- **2008 backtest.** Runs the same detector over the real 2008–09 bloom to measure how
  much warning it would actually have given.

There's deliberately no trained ML model: with one or two documented regional bloom
events there's nothing to learn from that wouldn't be memorised noise.
[DECISIONS.md](docs/DECISIONS.md) explains this and the other design choices.

## Status

A working prototype, not an operational warning system.

| Part | State |
|---|---|
| Daily intake check, 2018–2026 monthly history | Run against real Copernicus data |
| Trajectory, current projection, backtest logic | Tested on synthetic data only |
| Two dataset IDs (currents, daily 2008 archive) | Not yet confirmed |
| Intake coordinates, alert thresholds | Approximate / untuned |

The full list, and what's next, is in [ROADMAP.md](docs/ROADMAP.md).

## Repository

```
qatar_bloom_watch/        Python pipeline: fetch, detect, trajectory, projection, backtest
qatar_dashboard/          Static dashboard: one self-contained index.html, no server needed
qatar_dashboard_react/    The same dashboard in React + Vite (the deployed version)
docs/                     Architecture, design decisions, runbook, roadmap
```

## Running it

Python pipeline (needs a free [Copernicus Marine](https://marine.copernicus.eu) account):

```bash
cd qatar_bloom_watch
pip install -r requirements.txt
copernicusmarine login
python test_offline_logic.py   # offline tests, no login needed
python run_daily_watch.py      # the daily steps, in order
```

React dashboard:

```bash
cd qatar_dashboard_react
npm install
npm run dev      # http://localhost:5173
npm run build    # static site in dist/
```

More detail, including scheduling and Vercel deployment, is in the
[runbook](docs/RUNBOOK.md).

## Data

Chlorophyll-a from the [Copernicus Marine Service](https://marine.copernicus.eu)
ocean-colour products (multi-sensor, 4 km). Historical context for the 2008–09 event is
from Richlen et al., "The catastrophic 2008–2009 red tide in the Arabian gulf region",
*Harmful Algae* (2010).

## How this was built

I built this with help from an AI coding assistant (Claude). I directed the project,
made the design calls in [DECISIONS.md](docs/DECISIONS.md), and I run, test, and review
every part before it goes in. Where something is only tested on synthetic data or still
unverified, the code and docs say so.

## License

[MIT](LICENSE)
