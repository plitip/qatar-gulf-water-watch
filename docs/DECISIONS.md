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

**Hotspot = unusual for that spot at that time of year, not unusual for that day.**
A pixel counts when it's more than 3 standard deviations above its own normal (every day
of the same month in 2018–2025, compared as log10 because chlorophyll is heavily skewed),
above 3.0 mg/m³, and part of a patch of at least 4 touching pixels.

How this was reached, on real data in September 2026:
1. The first rule was "top 5% of today's scene and above 3.0 mg/m³". It flagged exactly
   462 pixels every day from 10 to 24 September, because a percentile flags ~5% of pixels
   by definition, and the nearest was always Doha's permanently murky shoreline, about
   6 km away. The trajectory was flat whatever happened offshore.
2. Comparing each pixel with a normal built from *monthly* averages still flagged hundreds
   of pixels a day. A single day swings much more than a month's average, so ordinary days
   looked extreme.
3. A normal built from *daily* data fixed it: the daily count now ranges from 0 to about 60
   pixels and the nearest patch moves (9 km to 168 km).
4. It still flags water near Doha on some days, and that looks real: the near-real-time and
   reprocessed products agree to within about 2% on the days they overlap, so it isn't a
   processing difference, and the monthly data shows August 2026 higher than any August
   since 2018 at all three intakes.

Why 3 standard deviations: the Gulf box has about 9,200 sea pixels, so 2 SD would flag
~210 pixels a day by chance alone, 3 SD about 12, and the patch rule removes most of those.
The 2008 backtest is the check on whether this is too strict or too loose.

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

**Vercel hosts the React dashboard; GitHub Actions runs the pipeline.** Vercel only serves
the built site. `.github/workflows/daily.yml` runs `python -m bloomwatch daily` every morning,
commits the results, and the commit makes Vercel rebuild. Free, and it runs with the laptop
off. Credentials live in GitHub's encrypted repository secrets
(`COPERNICUSMARINE_SERVICE_USERNAME` / `COPERNICUSMARINE_SERVICE_PASSWORD`), never in the
repo. The alternatives, if Actions ever can't reach Copernicus:
1. Laptop + Windows Task Scheduler running `python -m bloomwatch daily`, then `git push`. Only
   runs when the laptop is on.
2. Raspberry Pi or a VPS (Oracle Cloud Always Free is the free-forever option) with cron,
   then `git push`. Don't expose a home Pi directly to the internet; push and let Vercel
   serve it instead.

**The 2008 claim is tested against other years, not asserted.** The backtest found water
70–90 km from Dibba on 1, 19 and 22 August 2008, before the first report on about 25 August.
That only means something if the check doesn't find water there every August. So the same
check days (1, 4, … 22 August) were run for 14 other years: 2003–2007 and 2009–2017, which
leaves out 2008 itself and 2018–2025 (those years define "normal", so they'd look quiet by
construction). A check counts if it flags anything within 100 km of Dibba. Result: 2008 had
3 of 8, 2017 had 3 of 8, and the other 13 years had none. Honest limits: the 100 km radius
was chosen after seeing 2008's flags sit 70–90 km out, and other radii haven't been tried.
The site says the check "picked out" the water, not that it "flagged" or "warned": the
site's own flag rule is different (an intake far above its recent days, or water moving
steadily toward Qatar), and nothing warned anyone in 2008.

**Umm Al Houl's 2026 readings look local (checked 2026-09-26).** It was above its usual range
every month from January to June, and its yearly average has risen about 3% a year since
2018. Each intake's reading averages only the two or three sea squares nearest the intake,
and here it's two: one was up 59% for January to June against its own 2018–2025 normal,
the other 14%, while water 10–15 km away was up about 15%. The open central Gulf wasn't
unusually green in 2026, so it isn't a Gulf-wide change or a change in the satellite
product. It could be a real change in that stretch of water, or something near the shore
that satellites misread as chlorophyll, such as sediment. The page says both.

**Flags are recorded, not sent.** When the daily run flags something, it goes into
`data/alert_log.json` and onto the dashboard, with a review field that's filled in by hand
afterwards ("likely real" or "false alarm"). Nothing notifies anyone yet, and the site says
only what the system does. Keeping false alarms in a public log is deliberate: how often
the system is wrong is part of the result.

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
