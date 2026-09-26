# Runbook

## One-time setup (Windows)

```powershell
cd qatar_bloom_watch
python -m pip install -r requirements.txt
```

If the `copernicusmarine` CLI isn't on PATH (common with the python.org Windows installer),
call it by full path from your Python install's `Scripts` folder:

```powershell
$CM = "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\Scripts\copernicusmarine.exe"
& $CM login                      # only if credentials aren't saved yet
& $CM login --force-overwrite    # to replace saved credentials (e.g. after a password change)
```

Credentials are saved in `%USERPROFILE%\.copernicusmarine\`, outside the repo, and scripts use them automatically. On a server or in CI, set
`COPERNICUSMARINE_SERVICE_USERNAME` and `COPERNICUSMARINE_SERVICE_PASSWORD` as
environment variables or secrets instead.

Known setup errors:
- `copernicusmarine : The term ... is not recognized` means it isn't on PATH. Use the full
  path above.
- `No module named copernicusmarine.__main__` means `python -m copernicusmarine` doesn't
  work for this package. Use the `.exe`.
- The password prompt looks like it isn't accepting typing. It is: the input is just
  hidden. Type it and press Enter.
- `Could not connect to authentication system` is usually a transient network or login
  issue. If it never goes away, the network may be blocking Copernicus (some sandboxed
  cloud environments do).

## Daily run

```powershell
cd qatar_bloom_watch
python run_daily_watch.py
```

This runs `qatar_bloom_watch.py` → `scan_gulf_for_approaching_blooms.py` →
`scan_gulf_trajectory.py` → `update_dashboard_gulf_panel.py`. Afterwards, open
`qatar_dashboard\index.html` by double-clicking it. There's no server and no localhost;
it's a plain file.

Offline tests (no login needed): `python test_offline_logic.py`

## Scheduling on the laptop (Windows Task Scheduler)

Task Scheduler is built into Windows and runs a program on a schedule. Nothing in the
repo creates the task; it has to be set up by hand.

1. Start menu → "Task Scheduler" → **Create Basic Task**.
2. Name it (e.g. "Gulf Water Watch"). Trigger: **Daily**, mid-morning (data lags a day).
3. Action: **Start a program**.
   - Program/script: `python` (or the full path to `python.exe`)
   - Add arguments: `run_daily_watch.py`
   - Start in: the full path of this repo's `qatar_bloom_watch` folder
4. Finish. Optionally, under the task's Settings, enable "Run task as soon as possible
   after a scheduled start is missed" (runs are skipped while the laptop is off or
   asleep).

## React dashboard

```powershell
cd qatar_dashboard_react
npm install
npm run dev       # http://localhost:5173
npm run lint      # ESLint (React hooks rules)
npm run build     # static site in dist/
npm run preview   # serve dist/ with the production security headers
```

To show real trajectory data, copy `qatar_bloom_watch\gulf_bloom_trajectory.json` over
`qatar_dashboard_react\src\data\gulfTrajectory.json`.

## Hosting (Vercel)

The React dashboard deploys to Vercel from this repo. In the Vercel project settings, set
**Root Directory** to `qatar_dashboard_react`; everything else (Vite build, `dist/`
output, security headers) comes from `qatar_dashboard_react/vercel.json`. Every push to
`main` redeploys, and pull requests get preview URLs.

Vercel only serves files; it can't run the pipeline. Something with normal internet
access must run the scripts and push updated data. See the options in
[DECISIONS.md](DECISIONS.md#hosting-and-automation).
