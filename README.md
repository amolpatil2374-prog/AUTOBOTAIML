# Local ML Pipeline — Phase 1: Data Sync + Sufficiency Report

This is the foundation everything else (backtesting, strategy selection,
signal generation) gets built on top of. It does two things, safely and
repeatably, every day:

1. Pulls new rows from your Google Sheet's `chain_*`/`candles_*` tabs into
   local Parquet files (`data/chain_NIFTY.parquet`, etc.)
2. Reports exactly how much data exists, and gives a plain YES/NO verdict
   on whether there's enough to train anything without just fitting noise

## 1. One-time setup — Google Cloud service account

Python needs its own credentials to read your Sheet in the background,
without you clicking through an OAuth login every time.

1. Go to [console.cloud.google.com](https://console.cloud.google.com/) →
   create a new project (or use an existing one)
2. **APIs & Services → Library** → enable **Google Sheets API**
3. **APIs & Services → Credentials → Create Credentials → Service Account**
   → give it any name → skip optional role/access steps
4. Open the new service account → **Keys → Add Key → Create new key → JSON**
   → this downloads a `.json` file
5. Rename that file `service_account.json` and place it in this folder
6. Open your Google Sheet → **Share** → paste the service account's email
   (looks like `something@project-id.iam.gserviceaccount.com`, visible on
   the service account's page) → give it **Viewer** access

## 2. Install Python dependencies

```powershell
pip install -r requirements.txt
```

## 3. Configure

Open `config.py` and fill in:
- `SHEET_ID` — the same ID from your Sheet's URL used for the Apps Script bot
- `SERVICE_ACCOUNT_JSON` — should already point to the right place if you
  followed step 1 exactly

## 4. Test it manually first

```powershell
python run_daily.py
```

Check `logs/data_report.log` — you should see a report like:

```
NIFTY — chain data
Total rows: 775
Trading days with data: 1
Date range: 2026-09-14 to 2026-09-14
NOT READY for training: 1/20 trading days collected.
Roughly 19 more trading day(s) needed before this crosses even the minimum
floor — and crossing the floor means 'trainable without pure noise-fitting',
not 'reliable'.
```

**This is the file to check every day.** Everything else in this pipeline
exists in service of this eventually saying READY.

## 5. Set up "never look back" auto-run (Windows)

From an **Administrator** PowerShell prompt, in this folder:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup_task_scheduler.ps1
```

This installs two scheduled tasks:
- Runs at every login — if the laptop was off, crashed, or asleep, this is
  what catches it up the moment it's back
- Runs daily at 11:45 PM as the routine end-of-day sync

Both are configured to retry 3 times, 5 minutes apart, if a run fails —
Task Scheduler's own resilience, independent of the retry logic already
inside `sync_data.py` itself.

**What this cannot do, and no software can:** generate a live trading
signal while the laptop has no power or no network. If a real-time signal
system matters later, that piece needs something always-on — this pipeline
is correctly scoped to backtesting and daily strategy research, which are
not time-critical and tolerate the laptop being off perfectly well.

## 6. Monitoring dashboard

Every run of `run_daily.py` regenerates `dashboard.html` in this folder —
a single self-contained file, no server, no internet dependency. Open it
once in any browser and just refresh (or leave the tab open; it
auto-refreshes every 5 minutes on its own).

Shows: pipeline health (did the last run finish cleanly), each symbol's
progress toward the 20-day sufficiency threshold, a per-day row-count
chart (thin/partial days shown in yellow), **a KPI scorecard per symbol**
(see below), and a **Model & Strategy Results** section that's honestly
empty for now — that's Phase 2, and this placeholder won't be replaced
with anything fake in the meantime.

### KPI scorecard (automatic, gates before scores)

Implements the KPI & scoring framework as a live, self-updating check —
`kpi_scoring.py` computes it, `generate_dashboard.py` renders it. Two
gates are real right now:

- **G1 (infrastructure reliability)** — % of scheduled runs that
  completed cleanly, from `run_daily.log`
- **G2 (data volume)** — trading days collected vs. the 20-day floor

Three gates (G3 statistical significance, G4 sample size, G5 liquidity
feasibility) and the full Tier 1 composite score depend on Phase 2 model
output that doesn't exist yet — they honestly show **pending**, not a
fabricated number. The moment Phase 2 writes a
`data/model_results_<SYMBOL>.json` file matching the contract documented
at the top of `kpi_scoring.py`, these light up automatically — no changes
needed to this file when that day comes.

**The gating is all-or-nothing on purpose.** A single failed gate reports
the whole symbol as NOT READY and hides the Tier 1 score entirely, even
if every other number looks strong — this mirrors the framework's core
principle that a weighted average must never let one category's strength
paper over another's disqualifying failure.

## 7. Mobile / anywhere access via GitHub Pages

By default the dashboard is only a local file. To reach it from your phone
on mobile data (not just home WiFi), it needs to actually be published
somewhere on the internet — `run_daily.py` does this automatically via
GitHub Pages, once you set it up:

1. Create a free GitHub account if you don't have one, at github.com
2. Create a new **public** repository (e.g. `option-dashboard`) — public
   is required for free-tier Pages hosting. Note: this means the URL is
   reachable by anyone who has it, though it won't be indexed or listed
   anywhere. Fine for this content (sufficiency stats, no credentials);
   worth knowing if you ever add anything more sensitive to the dashboard.
3. In that repo: **Settings → Pages → Build and deployment → Source** →
   select **Deploy from a branch** → branch `main`, folder `/ (root)` → Save
4. Generate a token: **github.com → Settings (your account, not the repo)
   → Developer settings → Personal access tokens → Fine-grained tokens →
   Generate new token**. Give it **Contents: Read and write** access,
   scoped to just this one repository.
5. In `config.py`, fill in:
   - `GITHUB_TOKEN` — the token from step 4
   - `GITHUB_REPO` — e.g. `"yourusername/option-dashboard"`
   - `GITHUB_PAGES_BRANCH` — `"main"` (or whatever you picked in step 3)
6. Run `python run_daily.py` once — check the log for
   `Dashboard published successfully to https://yourusername.github.io/...`
7. Open that URL on your phone. GitHub Pages can take a minute or two to
   go live the very first time; after that, updates are near-instant.

**Keep `config.py` private** — don't commit it to a public repo or share
it, since it holds your GitHub token alongside the Sheet ID. Only
`dashboard.html`'s contents get pushed to GitHub, never the rest of this
project folder.

## 8. Running on GitHub Actions instead of the laptop (optional, recommended)

This pipeline runs once or twice a day — nothing latency-sensitive like the
1-minute option chain logger. That makes it a genuinely good fit for
**GitHub Actions**: your code runs on GitHub's own servers on a real
schedule, forever, for free, with **zero dependency on your laptop being
on, awake, or even in the same country.** This removes the single point
of failure the whole Task Scheduler setup was built around.

**One thing to decide upfront:** the accumulating data needs to live
inside the repo (committed automatically by each run) so it persists
between runs — Actions machines are wiped clean after every run
otherwise. Since the repo's already public for GitHub Pages, this means
your option-chain history sits in that same already-public place. Same
sensitivity level you already accepted for the dashboard itself.

### One-time setup

1. **Push this whole project folder to your GitHub repo** — the same one
   already serving the dashboard. Easiest way if you're not familiar with
   git: on the repo's GitHub page, **Add file → Upload files**, then
   drag in every file *except* `config.py` and `service_account.json`
   (those must never be uploaded — `.gitignore` already excludes them if
   you use git instead).
2. **Add two repository secrets** — repo page → **Settings → Secrets and
   variables → Actions → New repository secret**:
   - `GOOGLE_SERVICE_ACCOUNT_JSON` — paste the entire contents of your
     `service_account.json` file
   - `PIPELINE_SHEET_ID` — your Google Sheet ID (same one from `config.py`)
3. **Allow the workflow to push commits** — repo **Settings → Actions →
   General → Workflow permissions** → select **Read and write
   permissions** → Save.
4. **Test it manually** — repo → **Actions** tab → **Daily Pipeline Run**
   workflow → **Run workflow** button. Watch it execute in real time;
   click into the run to see the exact same log output you'd see locally.
5. Once that manual run succeeds, it's live — the `18:15 UTC` (23:45 IST)
   schedule in `.github/workflows/daily.yml` takes over from here with no
   further action needed.

### What happens to the Windows setup

Nothing forces you to remove it — running both in parallel for a while is
a reasonable way to build confidence before trusting Actions alone. When
you're ready, disabling the two Windows Scheduled Tasks (`taskschd.msc` →
right-click each → Disable) stops the laptop-side runs without deleting
anything, so it's easy to fall back if needed.

## Roadmap — what comes next

You asked to build the ML piece now and watch it day by day rather than
wait for "enough" data, understanding the overfitting risk. Here's how
that gets built responsibly on top of this foundation:

- **Phase 2 — Feature engineering + first-cut model.** Build features from
  the chain data (IV, delta, OI/volume deltas, PCR, etc.), train a simple,
  heavily-regularized classifier (not deep learning — that would be even
  more overfit-prone on limited data) using proper walk-forward
  validation (train on earlier days, test on later ones — never a random
  shuffle, which would leak future information backward). The daily report
  gets a new section: current model output, plus **a prominent
  "INSUFFICIENT DATA — exploratory only" banner on every single day's
  output until the sufficiency threshold above is actually crossed.** You
  see it working (or not) every day, exactly as asked, with the caveat
  never allowed to quietly disappear.
- **Phase 3 — Strategy backtest engine + signal generation.** A handful of
  named, interpretable options-buying strategies, backtested against
  accumulated history, with SL and trailing-profit rules attached.
- **Phase 4 — Paper P&L tracking.** Every signal the model would have
  generated, tracked forward against actual subsequent price data, so you
  can see real (simulated) performance accumulate over time before any
  real money follows a signal.

Each phase builds on data shapes verified from the previous one actually
running — same reason the Apps Script bot got built and tested step by
step rather than all at once.
