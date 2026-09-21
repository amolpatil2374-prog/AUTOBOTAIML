"""
For a given (threshold_pct, window_minutes) combination, labels every
option observation: did its price rise by at least threshold_pct within
window_minutes of that observation?

THE LEAKAGE GUARD IS THE WHOLE POINT OF THIS FILE. A label needs the
actual future price path to exist in already-collected data. An
observation whose window extends past the last data we have — including
right now, mid-day, for anything in the last `window_minutes` — CANNOT
be labeled yet. Those rows get label = NaN (excluded), never guessed,
never defaulted to 0. Skipping this is the single most common way a
backtest quietly lies to itself.

Windows longer than one trading day (2-day, 3-day, 1-week, 2-week) are
evaluated using calendar time, not trading-minutes-elapsed — "held for 3
days" means 3 real days passed, including the overnight gap where
nothing trades. This matches how a real position actually behaves.
"""
import pandas as pd

import config


def label_combination(features_df, threshold_pct, window_minutes):
    """features_df: output of feature_engineering.build_features().
    Returns the same df with two new columns: `label` (1/0/NaN) and
    `label_reason` (why NaN, when it is)."""
    df = features_df.sort_values(["strike", "option_type", "timestamp"]).copy()
    df["label"] = pd.NA
    df["label_reason"] = None

    last_known_time = df["timestamp"].max()

    for (strike, side), group in df.groupby(["strike", "option_type"], sort=False):
        group = group.sort_values("timestamp")
        times = group["timestamp"].values
        ltps = group["ltp"].values
        idx = group.index.values

        for i in range(len(group)):
            entry_time = times[i]
            entry_ltp = ltps[i]
            window_end = entry_time + pd.Timedelta(minutes=window_minutes)

            if pd.isna(entry_ltp) or entry_ltp <= 0:
                df.loc[idx[i], "label_reason"] = "no_entry_price"
                continue

            if window_end > last_known_time:
                # The leakage guard. We don't yet know what happens between
                # now and window_end — this row cannot be labeled today.
                df.loc[idx[i], "label_reason"] = "window_not_yet_elapsed"
                continue

            # Look forward within the window, same contract only.
            future_mask = (times > entry_time) & (times <= window_end)
            future_ltps = ltps[future_mask]
            future_ltps = future_ltps[~pd.isna(future_ltps)]

            if len(future_ltps) == 0:
                df.loc[idx[i], "label_reason"] = "no_future_data_in_window"
                continue

            target_price = entry_ltp * (1 + threshold_pct / 100)
            hit = (future_ltps >= target_price).any()
            df.loc[idx[i], "label"] = 1 if hit else 0
            df.loc[idx[i], "label_reason"] = "labeled"

    return df


def label_summary(labeled_df):
    """Quick counts — how many rows got a real label vs excluded, and why."""
    total = len(labeled_df)
    reason_counts = labeled_df["label_reason"].value_counts().to_dict()
    labeled = labeled_df["label"].notna().sum()
    win_rate = labeled_df["label"].mean() if labeled > 0 else None
    return {
        "total_rows": total,
        "labeled_rows": int(labeled),
        "exclusion_reasons": reason_counts,
        "win_rate": win_rate,
    }
