# Decisions and why

Each entry: what was decided, why, and what would change it. Read this before
"improving" something back into a mistake that's already been made and fixed once.

## Method

**Compare each intake to its own history, not a fixed threshold.**
The Gulf is shallow, dusty, and full of sediment. A single global chlorophyll cutoff
would give constant false alarms. Each site is judged against its own baseline, so an
alert means "unusual for this exact spot."

**Seasonal baseline: same calendar month, prior years.**
The monthly chart spikes every warm season, and if it always spikes, that spike is part
of the pattern, not an alarm. The stat tiles originally compared against all months
pooled together, which flagged every normal summer. They now compare,
say, this August against the previous 8 Augusts (mean ± 2 SD). August 2026 still comes
out above normal at all three sites under the stricter test.

**Don't compare Qatar's absolute values to other countries' plants.**
Absolute chlorophyll depends on depth, currents, and outflows, so it isn't comparable
across locations. What would be useful: adding a UAE site to the same pipeline to tell a
Qatar-only spike (local cause) from a Gulf-wide one (regional bloom). Offered, not built.

**Watch the wider Gulf, not just the intakes.**
Satellite data lags by a day or more, so looking only at the intakes is close to same-day
detection. Real lead time comes from seeing a patch in the wider Gulf days before it
drifts to Qatar. Hence `gulf.scan_today()` and then the multi-day
`gulf.track_trajectory()`: a single snapshot shows a hotspot exists, not that it's coming.

**Hotspot = above the 95th percentile AND above 3.0 mg/m³.**
A percentile alone flags junk on a uniformly murky day. A fixed floor alone ignores the
day's conditions. Both together means locally unusual and high in absolute terms.

**Known problem, found on real data (September 2026): the hotspot rule doesn't work as
intended yet.** From 10 to 24 September the scan found exactly 462 hotspots every day, and
the nearest one was about 6 km from Qatar, on Doha's own coast, on every day but one. Two
reasons. A 95th-percentile cutoff flags about 5% of the valid pixels by definition, so the
count barely moves unless the 3.0 mg/m³ floor kicks in. And shallow, murky coastal water
near Doha is always in that top 5%, so "nearest hotspot" is stuck on the coast and the
trajectory stays flat whatever happens offshore. Likely fixes: leave out a coastal band,
or compare each pixel with its own seasonal history (the same idea the intake check and
the dashboard already use) instead of with the rest of that day's scene.

**Trajectory tracks nearest-hotspot distance, not a tagged water patch.**
It's simpler, but if one patch fades near Qatar and an unrelated one appears farther out,
it can misread as "receding." This is documented in the script. A real fix is patch
tracking or optical flow (see NEXT_STEPS.md, later).

## "Prediction" and machine learning

**No trained ML model, on purpose.**
It was considered. Training needs labelled examples (what the data looked like →
what happened). There are about one or two documented regional bloom events and no
documented plant-level hit on Qatar. A model trained on that would memorise noise and look
more rigorous than it is. For a university pitch, that's a liability. Reviewers who know
the field will ask what the model learned.

**Instead: physics-based advection plus a historical backtest.**
- `projection.py` moves each hotspot along the sampled ocean current,
  held constant. It's labelled as a projection, not a forecast.
- `backtest.py` runs the real detector on real 2008 imagery and measures lead
  time against the documented first sighting. This is the project's strongest evidence,
  because it's checked against something that really happened.

**A legitimate "learned" upgrade, for later:** measure how elevated-chlorophyll patches
actually moved between consecutive days across years of daily imagery (optical-flow style).
That learns real movement patterns without needing bloom labels. It depends on the daily
reprocessed archive going back far enough.

**Other signals to pair with chlorophyll (phase 2, not built):**
- Sea surface temperature anomalies: Gulf blooms correlate with warm water, and
  Copernicus serves SST.
- Currents: for real advection (partly done in the projection script).
- Dissolved oxygen: a chlorophyll spike plus falling oxygen is a much more specific HAB
  signature.

Each one adds complexity. The call was to validate the chlorophyll-only version first.

## Hosting and automation

**The pipeline needs normal internet access.** Some sandboxed cloud environments block
Copernicus (proxy 403 on `auth.marine.copernicus.eu`), so any automated run has to happen
somewhere with ordinary outbound access.

**Vercel hosts the React dashboard; it's display only.** It serves the built static site
and runs nothing on a schedule. Something else has to fetch new data, rebuild, and push.
Options, all still open:
1. **GitHub Actions** on a cron schedule. Free. Runners have normal outbound internet, so
   Copernicus should be reachable (untested). Credentials go in GitHub Secrets as
   `COPERNICUSMARINE_SERVICE_USERNAME` / `COPERNICUSMARINE_SERVICE_PASSWORD`.
2. Laptop + Windows Task Scheduler running `python -m bloomwatch daily`, then `git push`. Only
   runs when the laptop is on.
3. Raspberry Pi or a VPS (Oracle Cloud Always Free is the free-forever option) with cron,
   then `git push`. Don't expose a home Pi directly to the internet; push and let Vercel
   serve it instead.

**Static dashboard embeds data instead of fetching it,** because `fetch()` of local JSON
fails under `file://`. On a real web host, fetching JSON would work, and it's a reasonable
refactor once hosting is decided.

**Email alerts were recommended early as the most useful next step** (the dashboard is for
looking; the alert is what makes it a tool). The `TODO` in `intake.py` is still
there. Not built.

## Style

**Domain-specific, explained code.** Generic names and section-title comments were
rewritten early: names say what they are (`DESAL_INTAKE_SITES`, `GULF_WATCH_BBOX`),
docstrings explain why, error messages say what to do next, and output goes through
logging. Keep it that way.
