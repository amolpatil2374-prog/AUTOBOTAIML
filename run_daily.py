"""
Main entry point. Task Scheduler calls this — nothing else needs to be run
by hand. Currently: sync data, then report on sufficiency.
Phase 2 (once built) will add model training/backtesting as a further step
here, gated behind data_report's readiness verdict.
"""
import logging
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="backslashreplace")

import config
import sync_data
import data_report
import train_model
import generate_dashboard
import publish_dashboard
from logging_setup import get_logger

log = get_logger("run_daily", "run_daily.log")

LOCK_PATH = os.path.join(config.STATE_DIR, "run_daily.lock")
LOCK_STALE_SECONDS = 30 * 60  # a lock older than this is assumed to be from a crashed run, not a live one


def acquire_lock():
    """Prevents two instances (e.g. a manual run overlapping a scheduled
    one) from writing to the same log/state/parquet files concurrently.
    Returns True if the lock was acquired, False if another run is
    genuinely still active."""
    os.makedirs(config.STATE_DIR, exist_ok=True)
    if os.path.exists(LOCK_PATH):
        age = time.time() - os.path.getmtime(LOCK_PATH)
        if age < LOCK_STALE_SECONDS:
            return False
        log.warning(f"Found a lock file {age:.0f}s old — treating as stale (from a crashed run) and continuing.")
    with open(LOCK_PATH, "w") as f:
        f.write(str(os.getpid()))
    return True


def release_lock():
    if os.path.exists(LOCK_PATH):
        os.remove(LOCK_PATH)


def main():
    if not acquire_lock():
        log.warning("Another run appears to already be in progress (lock file is recent) — skipping this invocation entirely rather than risking concurrent writes.")
        return

    try:
        _run()
    finally:
        release_lock()


def _run():
    log.info("=== Daily run starting ===")
    try:
        sync_data.main()
    except Exception as e:
        log.error(f"Sync step failed: {e}. Continuing to report on whatever data already exists locally.")

    try:
        data_report.main()
    except Exception as e:
        log.error(f"Report step failed: {e}")

    try:
        train_model.main()
    except Exception as e:
        log.error(f"Phase 2 model training failed: {e}. Dashboard will show whatever results, if any, were written before the failure.")

    dashboard_path = os.path.join(config.BASE_DIR, "dashboard.html")

    # First pass: generate + publish now, so something useful exists even
    # if this exact run never reaches the lines below (a genuine crash, not
    # just this run's own in-progress status).
    #
    # RUNNING_IN_GITHUB_ACTIONS: when true, the workflow's own git commit +
    # push already updates dashboard.html directly in the repo GitHub Pages
    # serves — the REST API publish step would just be a redundant, slower
    # way of doing the same thing, so it's skipped in that environment.
    running_in_actions = os.environ.get("GITHUB_ACTIONS") == "true"

    try:
        generate_dashboard.generate()
        log.info("Dashboard regenerated (pre-completion pass).")
    except Exception as e:
        log.error(f"Dashboard generation failed: {e}")

    if not running_in_actions:
        try:
            publish_dashboard.publish(dashboard_path)
        except Exception as e:
            log.error(f"Dashboard publish failed: {e}. Local dashboard.html is still up to date, just not published.")

    log.info("=== Daily run complete ===")

    # Second pass: regenerate (+ republish, outside Actions) AFTER logging
    # completion, so the dashboard's own "did the run finish" self-check
    # reflects reality rather than a snapshot taken mid-run, before
    # completion was even possible to have been logged yet.
    try:
        generate_dashboard.generate()
        if not running_in_actions:
            publish_dashboard.publish(dashboard_path)
    except Exception as e:
        log.error(f"Final dashboard refresh failed: {e}. The pre-completion version above is still live.")


if __name__ == "__main__":
    main()
