"""
Generates dashboard.html from local Parquet data — a single self-contained
file, no server process, no internet/CDN dependency. Regenerated every time
run_daily.py runs (login + nightly), so just keep the file open in a browser
tab and refresh (F5) to see the latest numbers.

Currently shows: data pipeline health, sufficiency progress per symbol, and
a per-day row-count chart to spot gaps at a glance. The "Model & Strategy
Results" section is an honest placeholder — there's no trained model yet
(that's Phase 2). It'll get real content once that exists, not fake content
now.
"""
import os
import html
from datetime import datetime

import pandas as pd

import config
import kpi_scoring

DASHBOARD_PATH = os.path.join(config.BASE_DIR, "dashboard.html")


def load_symbol_data(symbol):
    path = os.path.join(config.DATA_DIR, f"chain_{symbol}.parquet")
    if not os.path.exists(path):
        return None
    df = pd.read_parquet(path)
    if df.empty:
        return None
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["date"] = df["timestamp"].dt.date
    per_day = df.groupby("date").size().sort_index()
    return {
        "trading_days": len(per_day),
        "total_rows": len(df),
        "date_min": per_day.index.min(),
        "date_max": per_day.index.max(),
        "per_day": per_day,
        "thin_days": per_day[per_day < config.MIN_ROWS_PER_DAY_EXPECTED],
    }


def bar_chart_html(per_day):
    if per_day is None or len(per_day) == 0:
        return "<p class='muted'>No data yet.</p>"
    max_val = max(per_day.max(), 1)
    rows = []
    for date, count in per_day.items():
        pct = max(2, round(count / max_val * 100))
        thin = count < config.MIN_ROWS_PER_DAY_EXPECTED
        bar_class = "bar thin" if thin else "bar"
        rows.append(
            f"<div class='bar-row'>"
            f"<span class='bar-label'>{date}</span>"
            f"<div class='bar-track'><div class='{bar_class}' style='width:{pct}%'></div></div>"
            f"<span class='bar-value'>{count}</span>"
            f"</div>"
        )
    return "\n".join(rows)


def symbol_section_html(symbol):
    d = load_symbol_data(symbol)
    if d is None:
        return f"""
        <div class="card">
          <h2>{symbol}</h2>
          <p class="muted">No data synced yet.</p>
        </div>"""

    ready = d["trading_days"] >= config.MIN_TRADING_DAYS_FOR_TRAINING
    pct = min(100, round(d["trading_days"] / config.MIN_TRADING_DAYS_FOR_TRAINING * 100))
    status_class = "ready" if ready else "not-ready"
    status_text = "READY" if ready else "NOT READY"

    thin_html = ""
    if len(d["thin_days"]) > 0:
        items = "".join(f"<li>{date}: {count} rows</li>" for date, count in d["thin_days"].items())
        thin_html = f"""
        <div class="warning">
          <strong>{len(d['thin_days'])} thin day(s)</strong> (fewer than {config.MIN_ROWS_PER_DAY_EXPECTED} rows —
          check error_log for that date):
          <ul>{items}</ul>
        </div>"""

    return f"""
    <div class="card">
      <h2>{symbol}</h2>
      <div class="status-badge {status_class}">{status_text}</div>
      <div class="stat-grid">
        <div><span class="stat-label">Trading days</span><span class="stat-value">{d['trading_days']} / {config.MIN_TRADING_DAYS_FOR_TRAINING}</span></div>
        <div><span class="stat-label">Total rows</span><span class="stat-value">{d['total_rows']:,}</span></div>
        <div><span class="stat-label">Date range</span><span class="stat-value">{d['date_min']} to {d['date_max']}</span></div>
      </div>
      <div class="progress-track"><div class="progress-fill" style="width:{pct}%"></div></div>
      {thin_html}
      <h3>Rows per day</h3>
      <div class="bar-chart">{bar_chart_html(d['per_day'])}</div>
    </div>"""


def last_run_status_html():
    log_path = os.path.join(config.LOG_DIR, "run_daily.log")
    if not os.path.exists(log_path):
        return "<p class='muted'>No run log found yet.</p>"
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    last_lines = lines[-15:] if len(lines) > 15 else lines
    completed = any("Daily run complete" in l for l in last_lines)
    status_class = "ready" if completed else "not-ready"
    status_text = "Last run completed cleanly" if completed else "Last run may not have finished — check logs"
    tail = html.escape("".join(last_lines))
    return f"""
      <div class="status-badge {status_class}">{status_text}</div>
      <pre class="log-tail">{tail}</pre>"""


def kpi_section_html(symbol):
    report = kpi_scoring.score_symbol(symbol)
    overall_class = "ready" if report["overall"] == "READY" else "not-ready"

    gate_rows = []
    for g in report["gates"]:
        icon = {"pass": "&#10003;", "fail": "&#10007;", "pending": "&#8230;"}[g["status"]]
        gate_rows.append(
            f"<div class='gate-row gate-{g['status']}'>"
            f"<span class='gate-icon'>{icon}</span>"
            f"<span class='gate-name'>{g['gate']}</span>"
            f"<span class='gate-detail'>{html.escape(g['detail'])}</span>"
            f"</div>"
        )

    tier1_html = "<p class='muted'>Tier 1 score locked until all Tier 0 gates pass.</p>"
    if report["tier1"]:
        t1 = report["tier1"]
        cat_rows = "".join(
            f"<div class='bar-row'><span class='bar-label'>{cat}</span>"
            f"<div class='bar-track'><div class='bar' style='width:{score}%'></div></div>"
            f"<span class='bar-value'>{score}</span></div>"
            for cat, score in t1["categories"].items()
        )
        tier1_html = f"""
        <div class="tier1-score">{t1['composite']}<span class="tier1-max">/100</span></div>
        <div class="tier1-verdict">{t1['verdict']}</div>
        <div class="bar-chart">{cat_rows}</div>"""

    return f"""
    <div class="card">
      <h2>{symbol} — KPI Scorecard</h2>
      <div class="status-badge {overall_class}">{report['overall']}</div>
      <h3>Tier 0 gates</h3>
      <div class="gate-list">{''.join(gate_rows)}</div>
      <h3>Tier 1 composite score</h3>
      {tier1_html}
    </div>"""


def generate():
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    symbol_sections = "".join(symbol_section_html(s) for s in config.SYMBOLS)
    kpi_sections = "".join(kpi_section_html(s) for s in config.SYMBOLS)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="300">
<title>Option Chain Pipeline — Dashboard</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Arial, sans-serif; background: #0f1115; color: #e6e6e6; margin: 0; padding: 24px; }}
  h1 {{ font-size: 22px; margin-bottom: 4px; }}
  .generated {{ color: #888; font-size: 13px; margin-bottom: 24px; }}
  .card {{ background: #171a21; border: 1px solid #2a2e38; border-radius: 10px; padding: 20px; margin-bottom: 20px; }}
  .card h2 {{ margin-top: 0; }}
  .status-badge {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 600; margin-bottom: 14px; }}
  .status-badge.ready {{ background: #1e3a2a; color: #4ade80; }}
  .status-badge.not-ready {{ background: #3a2a1e; color: #fbbf24; }}
  .stat-grid {{ display: flex; gap: 32px; margin-bottom: 14px; flex-wrap: wrap; }}
  .stat-label {{ display: block; color: #888; font-size: 12px; }}
  .stat-value {{ display: block; font-size: 18px; font-weight: 600; }}
  .progress-track {{ background: #2a2e38; border-radius: 6px; height: 10px; overflow: hidden; margin-bottom: 14px; }}
  .progress-fill {{ background: #4ade80; height: 100%; }}
  .warning {{ background: #2a2114; border: 1px solid #5a4a1e; border-radius: 6px; padding: 10px 14px; margin-bottom: 14px; font-size: 13px; }}
  .warning ul {{ margin: 6px 0 0 0; padding-left: 20px; }}
  .bar-chart {{ margin-top: 8px; }}
  .bar-row {{ display: flex; align-items: center; gap: 10px; margin-bottom: 4px; font-size: 12px; }}
  .bar-label {{ width: 100px; color: #aaa; flex-shrink: 0; }}
  .bar-track {{ flex-grow: 1; background: #2a2e38; border-radius: 4px; overflow: hidden; height: 14px; }}
  .bar {{ background: #4ade80; height: 100%; }}
  .bar.thin {{ background: #fbbf24; }}
  .bar-value {{ width: 50px; text-align: right; color: #ccc; flex-shrink: 0; }}
  .muted {{ color: #888; }}
  .placeholder {{ color: #888; font-style: italic; padding: 20px; text-align: center; border: 1px dashed #3a3e48; border-radius: 8px; }}
  .log-tail {{ background: #0a0c10; border-radius: 6px; padding: 12px; font-size: 12px; overflow-x: auto; max-height: 250px; overflow-y: auto; }}
  .gate-list {{ display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px; }}
  .gate-row {{ display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-radius: 6px; font-size: 13px; }}
  .gate-pass {{ background: #1e3a2a; }}
  .gate-fail {{ background: #3a1e1e; }}
  .gate-pending {{ background: #2a2a2e; }}
  .gate-icon {{ width: 18px; text-align: center; font-weight: 600; }}
  .gate-pass .gate-icon {{ color: #4ade80; }}
  .gate-fail .gate-icon {{ color: #f87171; }}
  .gate-pending .gate-icon {{ color: #888; }}
  .gate-name {{ font-weight: 600; width: 30px; flex-shrink: 0; }}
  .gate-detail {{ color: #ccc; }}
  .tier1-score {{ font-size: 42px; font-weight: 600; color: #4ade80; }}
  .tier1-max {{ font-size: 18px; color: #888; }}
  .tier1-verdict {{ font-size: 14px; color: #ccc; margin-bottom: 14px; }}
</style>
</head>
<body>
  <h1>Option Chain Pipeline — Dashboard</h1>
  <div class="generated">Generated {generated_at} — auto-refreshes every 5 minutes while this tab stays open. Re-run run_daily.py (or wait for the next scheduled run) to update the underlying data.</div>

  <div class="card">
    <h2>Pipeline Health</h2>
    {last_run_status_html()}
  </div>

  {symbol_sections}

  {kpi_sections}

  <div class="card">
    <h2>Model &amp; Strategy Results</h2>
    <div class="placeholder">
      Not built yet — this is Phase 2. Once a model exists, its signals, backtest performance,
      and the data-sufficiency banner will appear here. Showing nothing is more honest than
      showing something fake.
    </div>
  </div>
</body>
</html>"""

    with open(DASHBOARD_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)


if __name__ == "__main__":
    generate()
    print(f"Dashboard written to {DASHBOARD_PATH}")
