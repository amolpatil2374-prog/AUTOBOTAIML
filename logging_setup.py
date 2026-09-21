"""
Sets up a named logger with its own handlers, attached directly to that
logger rather than the shared root logger. logging.basicConfig() only has
an effect the FIRST time it's called in a process — every module using it
independently silently loses to whichever module got imported first. That
bug is exactly why run_daily.log came back empty: sync_data's basicConfig
call claimed the root logger first, and run_daily.py's own call
afterward did nothing, so its messages went to sync.log all along.

propagate = False stops messages from also bubbling up to the root logger
(which would double-print them if the root ever gets its own handlers).
"""
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone


def now_ist():
    """Current time in India (IST), no matter which computer/timezone this
    code actually runs on — needed because GitHub Actions runs on UTC time,
    while a Windows laptop set to India time does not need this, but using
    this everywhere keeps both places always showing the same, correct
    India time without depending on the computer's own clock setting."""
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)


def _ist_time_converter(timestamp):
    """Makes every log line's own timestamp (the part logging writes
    automatically, e.g. "2026-09-13 14:37:56") show IST too — without this,
    the log FILE's timestamps still show the computer's own clock (UTC on
    GitHub Actions), even though now_ist() above fixes other places."""
    return time.gmtime(timestamp + 5.5 * 3600)

import config


def get_logger(name, log_filename, fmt="%(asctime)s [%(levelname)s] %(message)s"):
    log = logging.getLogger(name)
    log.setLevel(logging.INFO)
    log.propagate = False

    if not log.handlers:  # avoid double handlers if a module is ever imported twice
        os.makedirs(config.LOG_DIR, exist_ok=True)
        formatter = logging.Formatter(fmt)
        formatter.converter = _ist_time_converter

        fh = logging.FileHandler(os.path.join(config.LOG_DIR, log_filename), encoding="utf-8")
        fh.setFormatter(formatter)
        log.addHandler(fh)

        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        log.addHandler(sh)

    return log
