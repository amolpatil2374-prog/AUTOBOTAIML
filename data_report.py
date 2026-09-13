"""
Reads the local Parquet files and reports, per symbol:
  - how many distinct trading days of chain data exist
  - total row count and date range
  - any days with a suspiciously low row count (partial/broken log day)
  - a clear, unambiguous "ready for training" verdict

This is the thing to actually look at each day while data accumulates —
everything else in this pipeline is plumbing in service of this report
eventually saying YES instead of NO.
"""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="backslashreplace")
import logging
from datetime import datetime

import pandas as pd

import config
from logging_setup import get_logger

log = get_logger("report", "data_report.log", fmt="%(message)s")


def compute_symbol_stats(symbol):
    """Pure computation, no logging — returns a stats dict or None if no data
    exists yet. Shared by report_for_symbol() below and by kpi_scoring.py,
    so trading-day counting logic lives in exactly one place."""
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
        "ready": len(per_day) >= config.MIN_TRADING_DAYS_FOR_TRAINING,
    }


def report_for_symbol(symbol):
    log.info(f"\n{'=' * 60}\n{symbol} — chain data\n{'=' * 60}")

    stats = compute_symbol_stats(symbol)
    if stats is None:
        log.info("No data synced yet. Run sync_data.py first.")
        return {"symbol": symbol, "ready": False, "trading_days": 0}

    log.info(f"Total rows: {stats['total_rows']}")
    log.info(f"Trading days with data: {stats['trading_days']}")
    log.info(f"Date range: {stats['date_min']} to {stats['date_max']}")

    if len(stats["thin_days"]) > 0:
        log.info(f"\nWARNING: {len(stats['thin_days'])} day(s) with fewer than {config.MIN_ROWS_PER_DAY_EXPECTED} rows "
                  f"(possible partial log day — worth checking error_log for that date):")
        for d, count in stats["thin_days"].items():
            log.info(f"    {d}: {count} rows")

    log.info(f"\n{'READY' if stats['ready'] else 'NOT READY'} for training: "
              f"{stats['trading_days']}/{config.MIN_TRADING_DAYS_FOR_TRAINING} trading days collected.")
    if not stats["ready"]:
        remaining = config.MIN_TRADING_DAYS_FOR_TRAINING - stats["trading_days"]
        log.info(f"Roughly {remaining} more trading day(s) needed before this crosses even the minimum floor — "
                  f"and crossing the floor means 'trainable without pure noise-fitting', not 'reliable'.")

    return {"symbol": symbol, "ready": stats["ready"], "trading_days": stats["trading_days"], "total_rows": stats["total_rows"]}


def main():
    log.info(f"Data sufficiency report — {datetime.now():%Y-%m-%d %H:%M}")
    results = [report_for_symbol(s) for s in config.SYMBOLS]

    log.info(f"\n{'=' * 60}\nSUMMARY\n{'=' * 60}")
    for r in results:
        status = "READY" if r["ready"] else "NOT READY"
        log.info(f"  {r['symbol']}: {status} ({r.get('trading_days', 0)} trading days)")


if __name__ == "__main__":
    main()
