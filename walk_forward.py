"""
Expanding-window walk-forward evaluation: for each trading day (from the
second day onward), train a simple model on every day strictly before it,
test on that day alone. This is the only honest way to evaluate a
strategy against time-series data — a random train/test split would let
the model implicitly see the future, which is exactly the "graded on
questions you already saw the answers to" trap described in the project's
learning materials.

With very little real data (a handful of days), this will correctly
produce very few folds — that's accurate reporting of a genuine
data-volume problem, not a bug to paper over.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

FEATURE_COLS = [
    "iv", "delta", "gamma", "theta", "vega",
    "oi", "oi_delta", "volume", "volume_delta",
    "pcr_in_range", "moneyness", "spread_pct",
    "days_to_expiry", "minutes_since_midnight", "day_of_week",
]


def _prepare_xy(df):
    """Drops rows with any missing feature or missing label — a simple,
    conservative choice for a first-cut model. Returns (X, y, filtered_df)
    — the filtered dataframe is returned too so callers can correctly
    index back into the SAME rows X/y came from, not the original
    unfiltered input (a real bug caught during testing: indexing the
    original df with a mask sized for the filtered one silently
    misaligns everything downstream)."""
    usable = df.dropna(subset=FEATURE_COLS + ["label"])
    if len(usable) == 0:
        return None, None, None
    X = usable[FEATURE_COLS].astype(float).values
    y = usable["label"].astype(int).values
    return X, y, usable


def walk_forward_evaluate(labeled_df, window_minutes, min_train_rows=30, embargo_multiplier=2):
    """Returns a dict: overall_win_rate (of the model's own predictions
    being correct on held-out days), total_signals, signals_per_fold,
    baseline (always 0.5 for a binary win/loss label), and the raw
    per-fold results for further inspection.

    min_train_rows: a fold is skipped if there isn't even this many
    labeled training rows yet — avoids fitting a model on a near-empty
    prior history and calling the result meaningful.

    PURGING (per López de Prado's "Advances in Financial Machine
    Learning" — the standard reference for exactly this problem): a
    training row's label is only known once its full window has played
    out. If that window extends past the start of the test day, the
    label was computed using price action that happened during the test
    period — the model would be training on a sneak preview of the very
    thing it's being tested on. Any such row is purged from training.
    embargo_multiplier widens this by extra window-lengths as a buffer
    for feature autocorrelation (the literature recommends denominating
    the buffer in the label horizon itself, since that's the one
    quantity we know precisely without having to estimate anything)."""
    df = labeled_df.dropna(subset=["label"]).copy()
    if df.empty:
        return {"overall_win_rate": None, "total_signals": 0, "signals_per_fold": [], "baseline": 0.5, "folds": []}

    df["trade_date"] = df["timestamp"].dt.date
    days = sorted(df["trade_date"].unique())
    purge_buffer = pd.Timedelta(minutes=window_minutes * embargo_multiplier)

    fold_results = []
    signal_row_frames = []
    for i in range(1, len(days)):
        test_day = days[i]
        train_days = days[:i]
        test_day_start = pd.Timestamp(test_day)

        train_df_raw = df[df["trade_date"].isin(train_days)]
        # PURGE: drop any training row whose label window reaches into the
        # embargo buffer before the test day even starts.
        train_df = train_df_raw[train_df_raw["timestamp"] + purge_buffer <= test_day_start]
        n_purged = len(train_df_raw) - len(train_df)
        test_df = df[df["trade_date"] == test_day]

        X_train, y_train, _ = _prepare_xy(train_df)
        X_test, y_test, test_df_filtered = _prepare_xy(test_df)

        if X_train is None or X_test is None or len(X_train) < min_train_rows or len(X_test) == 0:
            continue
        if len(np.unique(y_train)) < 2:
            continue  # can't fit a classifier on all-one-class training data

        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        model = LogisticRegression(C=1.0, max_iter=1000)
        model.fit(X_train_scaled, y_train)
        predictions = model.predict(X_test_scaled)

        # What actually matters for a trading strategy isn't blanket
        # accuracy (which rewards trivially saying "don't buy" on most
        # rows) — it's precision on the rows the model actually chose to
        # buy. A fold where the model predicts zero buys is valid (it just
        # sat out that day), not an error.
        buy_mask = predictions == 1
        n_signals_raw = int(buy_mask.sum())

        # THE FIX: a real trader can only hold one position per contract at
        # a time. Without this, a single continuous move gets counted as
        # dozens of "separate" overlapping signals on the same contract —
        # confirmed as a real bug in this exact code via a synthetic test
        # (one 60-minute opportunity was counting as 60 signals). Keep only
        # non-overlapping signals per (strike, option_type): once a
        # position is "open," skip further signals on that same contract
        # until its window has closed.
        if n_signals_raw > 0:
            test_rows_all = test_df_filtered.iloc[buy_mask].copy()
            test_rows_all = test_rows_all.sort_values(["strike", "option_type", "timestamp"])
            keep_indices = []
            last_open_until = {}
            for idx, row in test_rows_all.iterrows():
                key = (row["strike"], row["option_type"])
                if key not in last_open_until or row["timestamp"] >= last_open_until[key]:
                    keep_indices.append(idx)
                    last_open_until[key] = row["timestamp"] + pd.Timedelta(minutes=window_minutes)
            test_rows = test_rows_all.loc[keep_indices]
        else:
            test_rows = test_df_filtered.iloc[0:0]

        n_signals = len(test_rows)
        signal_row_frames.append(test_rows)

        if n_signals == 0:
            fold_results.append({
                "test_day": str(test_day), "n_train": len(X_train), "n_test": len(X_test),
                "n_signals": 0, "n_correct": 0, "precision": None, "n_train_rows_purged": n_purged,
            })
            continue

        y_test_kept = test_rows["label"].astype(int).values
        correct = int((y_test_kept == 1).sum())
        fold_results.append({
            "test_day": str(test_day),
            "n_train": len(X_train),
            "n_test": len(X_test),
            "n_signals": n_signals,
            "n_signals_before_overlap_filter": n_signals_raw,
            "n_train_rows_purged": n_purged,
            "n_correct": correct,
            "precision": correct / n_signals,
        })

    if not fold_results:
        return {"overall_win_rate": None, "total_signals": 0, "signals_per_fold": [], "baseline": 0.5, "folds": [], "signal_rows": pd.DataFrame()}

    signal_folds = [f for f in fold_results if f["n_signals"] > 0]
    total_correct = sum(f["n_correct"] for f in signal_folds)
    total_signals = sum(f["n_signals"] for f in signal_folds)
    signal_rows = pd.concat(signal_row_frames, ignore_index=True) if signal_row_frames else pd.DataFrame()

    return {
        "overall_win_rate": (total_correct / total_signals) if total_signals > 0 else None,
        "total_signals": total_signals,
        "signals_per_fold": [f["n_signals"] for f in fold_results],
        "baseline": 0.5,
        "folds": fold_results,
        "signal_rows": signal_rows,  # the ACTUAL out-of-sample rows the model bought — use THIS for economics/risk
    }
