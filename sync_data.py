"""
Syncs the Google Sheet's chain_<SYMBOL>_<DATE> and candles_<SYMBOL>_<DATE>
tabs down to local Parquet files, one per symbol+kind, e.g.:
    data/chain_NIFTY.parquet
    data/candles_CRUDEOILM.parquet

Safe to rerun any time — for each tab, only rows beyond what's already been
synced (tracked in state/sync_state.json) are appended. Running this twice
in a row, or after a crash mid-run, does not duplicate data.

Deliberately does NOT try to be "smart" about partial-tab reads mid-write —
Apps Script only appends to these tabs, never rewrites earlier rows, so a
simple "rows synced so far" watermark per tab is sufficient and correct.
"""
import json
import logging
import os
import sys

# Windows' default console codepage (cp1252 etc.) can't encode every
# Unicode character — rather than crash mid-run if any log message ever
# contains one (as one did tonight), degrade gracefully instead.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="backslashreplace")
import time

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

import config
from logging_setup import get_logger

log = get_logger("sync", "sync.log")

STATE_PATH = os.path.join(config.STATE_DIR, "sync_state.json")


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, "r") as f:
            return json.load(f)
    return {}


def save_state(state):
    os.makedirs(config.STATE_DIR, exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def get_client(retries=5):
    for attempt in range(1, retries + 1):
        try:
            creds = Credentials.from_service_account_file(
                config.SERVICE_ACCOUNT_JSON,
                scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
            )
            return gspread.authorize(creds)
        except Exception as e:
            wait = min(30, 2 ** attempt)
            log.warning(f"Auth attempt {attempt}/{retries} failed: {e}. Retrying in {wait}s.")
            time.sleep(wait)
    raise RuntimeError("Could not authenticate to Google Sheets after repeated attempts.")


def matching_tabs(sheet):
    """Find every tab that looks like chain_<SYMBOL>_<DATE> or candles_<SYMBOL>_<DATE>."""
    matches = []
    for ws in sheet.worksheets():
        for kind in config.TAB_KINDS:
            for symbol in config.SYMBOLS:
                prefix = f"{kind}_{symbol}_"
                if ws.title.startswith(prefix):
                    matches.append((kind, symbol, ws))
    return matches


def sync_tab(kind, symbol, worksheet, state):
    tab_name = worksheet.title
    already_synced = state.get(tab_name, 0)  # number of DATA rows (excluding header) already pulled

    try:
        all_values = worksheet.get_all_values()
    except Exception as e:
        log.error(f"{tab_name}: failed to read — {e}. Will retry next run.")
        return 0

    if len(all_values) < 2:
        return 0  # header only, or empty — nothing to sync yet

    header = all_values[0]
    data_rows = all_values[1:]

    new_rows = data_rows[already_synced:]
    if not new_rows:
        return 0

    df_new = pd.DataFrame(new_rows, columns=header)
    df_new["_source_tab"] = tab_name  # keep provenance — which day's tab this came from

    local_path = os.path.join(config.DATA_DIR, f"{kind}_{symbol}.parquet")
    if os.path.exists(local_path):
        df_existing = pd.read_parquet(local_path)
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_combined = df_new

    os.makedirs(config.DATA_DIR, exist_ok=True)
    df_combined.to_parquet(local_path, index=False)

    state[tab_name] = len(data_rows)
    log.info(f"{tab_name}: synced {len(new_rows)} new rows (total now {len(data_rows)}).")
    return len(new_rows)


def main():
    os.makedirs(config.LOG_DIR, exist_ok=True)
    log.info("=== Sync run starting ===")

    client = get_client()
    sheet = client.open_by_key(config.SHEET_ID)
    state = load_state()

    tabs = matching_tabs(sheet)
    log.info(f"Found {len(tabs)} matching tabs.")

    total_new = 0
    for kind, symbol, worksheet in tabs:
        total_new += sync_tab(kind, symbol, worksheet, state)
        save_state(state)  # save after every tab — a crash mid-run loses no already-synced progress

    log.info(f"=== Sync run complete: {total_new} new rows total ===")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.critical(f"Fatal error during sync: {e}", exc_info=True)
        sys.exit(1)
