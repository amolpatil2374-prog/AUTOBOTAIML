"""
Turns the raw chain_<SYMBOL>.parquet (one row per strike per minute, CE and
PE side by side) into one row per OPTION OBSERVATION — a single strike,
a single side (CE or PE), at a single moment. This is the shape both
label construction and the model itself need: each row is one candidate
"if I'd bought this exact option at this exact moment" case.

Adds derived features (moneyness, spread, time-to-expiry, time-of-day)
on top of what's already logged (IV, Greeks, OI/volume deltas, PCR).
"""
import pandas as pd

import config

# Columns shared across CE and PE at the same strike/timestamp — carried
# over unchanged onto both melted rows.
SHARED_COLS = ["timestamp", "expiry", "underlying_ltp", "futures_underlying",
               "greeks_underlying", "greeks_underlying_method", "pcr_in_range", "strike"]

# (output feature name) -> (CE column, PE column) — same underlying concept,
# different column per side in the raw data.
SIDE_COLS = {
    "oi": ("CE_oi", "PE_oi"),
    "oi_delta": ("CE_oi_delta", "PE_oi_delta"),
    "volume": ("CE_volume", "PE_volume"),
    "volume_delta": ("CE_volume_delta", "PE_volume_delta"),
    "bid": ("CE_bid", "PE_bid"),
    "ask": ("CE_ask", "PE_ask"),
    "ltp": ("CE_ltp", "PE_ltp"),
    "iv": ("CE_iv", "PE_iv"),
    "delta": ("CE_delta", "PE_delta"),
    "gamma": ("CE_gamma", "PE_gamma"),
    "theta": ("CE_theta", "PE_theta"),
    "vega": ("CE_vega", "PE_vega"),
    "stale_min": ("CE_stale_min", "PE_stale_min"),
}


def melt_to_observations(df):
    """One row per (timestamp, strike, option_type). Returns a fresh df —
    does not modify the input."""
    ce = df[SHARED_COLS].copy()
    ce["option_type"] = "CE"
    for feat, (ce_col, pe_col) in SIDE_COLS.items():
        ce[feat] = df[ce_col]

    pe = df[SHARED_COLS].copy()
    pe["option_type"] = "PE"
    for feat, (ce_col, pe_col) in SIDE_COLS.items():
        pe[feat] = df[pe_col]

    melted = pd.concat([ce, pe], ignore_index=True)
    melted["timestamp"] = pd.to_datetime(melted["timestamp"], errors="coerce")
    melted["expiry"] = pd.to_datetime(melted["expiry"], errors="coerce")
    return melted


def add_derived_features(df):
    """Adds moneyness, spread, time-to-expiry, time-of-day — all computed
    from columns already present, no new data needed."""
    df = df.copy()

    df["moneyness"] = (df["strike"] - df["greeks_underlying"]) / df["greeks_underlying"]

    # Spread as a fraction of LTP — a liquidity signal. NaN/inf-safe: if
    # ltp is 0 or missing, spread_pct is left as NaN rather than dividing
    # by zero or fabricating a number.
    spread = df["ask"] - df["bid"]
    df["spread_pct"] = spread.where(df["ltp"] > 0, other=pd.NA) / df["ltp"].where(df["ltp"] > 0, other=pd.NA)

    # Time to expiry, in days (float) — 15:30 IST cutoff on expiry day,
    # matching the convention already used in the Apps Script Greeks math.
    expiry_cutoff = df["expiry"] + pd.Timedelta(hours=10)  # 15:30 IST = 10:00 UTC
    df["days_to_expiry"] = (expiry_cutoff - df["timestamp"]).dt.total_seconds() / (3600 * 24)
    df["days_to_expiry"] = df["days_to_expiry"].clip(lower=0)

    df["minutes_since_midnight"] = df["timestamp"].dt.hour * 60 + df["timestamp"].dt.minute
    df["day_of_week"] = df["timestamp"].dt.dayofweek  # 0=Monday

    return df


def build_features(symbol):
    """Loads chain_<SYMBOL>.parquet, returns the fully-featured observation
    table. Returns None if no data exists yet."""
    path = f"{config.DATA_DIR}/chain_{symbol}.parquet"
    try:
        df = pd.read_parquet(path)
    except FileNotFoundError:
        return None
    if df.empty:
        return None

    # The raw sheet data comes through as strings (Sheets API returns text) —
    # coerce the numeric columns before melting, or every downstream
    # calculation silently breaks on string arithmetic.
    numeric_cols = [c for c in df.columns if c not in ("timestamp", "expiry", "greeks_underlying_method", "_source_tab")]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    melted = melt_to_observations(df)
    featured = add_derived_features(melted)
    return featured


if __name__ == "__main__":
    for sym in config.SYMBOLS:
        feats = build_features(sym)
        if feats is None:
            print(f"{sym}: no data yet")
        else:
            print(f"{sym}: {len(feats)} observations, columns: {list(feats.columns)}")
