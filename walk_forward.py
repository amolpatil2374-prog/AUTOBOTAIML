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


def walk_forward_evaluate(labeled_df, min_train_rows=30):
    """Returns a dict: overall_win_rate (of the model's own predictions
    being correct on held-out days), total_signals, signals_per_fold,
    baseline (always 0.5 for a binary win/loss label), and the raw
    per-fold results for further inspection.

    min_train_rows: a fold is skipped if there isn't even this many
    labeled training rows yet — avoids fitting a model on a near-empty
    prior history and calling the result meaningful."""
    df = labeled_df.dropna(subset=["label"]).copy()
    if df.empty:
        return {"overall_win_rate": None, "total_signals": 0, "signals_per_fold": [], "baseline": 0.5, "folds": []}

    df["trade_date"] = df["timestamp"].dt.date
    days = sorted(df["trade_date"].unique())

    fold_results = []
    signal_row_frames = []
    for i in range(1, len(days)):
        test_day = days[i]
        train_days = days[:i]

        train_df = df[df["trade_date"].isin(train_days)]
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
        n_signals = int(buy_mask.sum())

        # Keep the actual out-of-sample rows the model would have bought —
        # this is what economics/risk analysis must be computed on, NOT
        # the full labeled dataset. Buying "everything" and buying "what
        # the model actually signals" are different populations with
        # different real economics; conflating them was a real bug caught
        # by checking this output carefully rather than trusting it.
        test_rows = test_df_filtered.iloc[buy_mask] if n_signals > 0 else test_df_filtered.iloc[0:0]
        signal_row_frames.append(test_rows)

        if n_signals == 0:
            fold_results.append({
                "test_day": str(test_day), "n_train": len(X_train), "n_test": len(X_test),
                "n_signals": 0, "n_correct": 0, "precision": None,
            })
            continue

        correct = int((y_test[buy_mask] == 1).sum())
        fold_results.append({
            "test_day": str(test_day),
            "n_train": len(X_train),
            "n_test": len(X_test),
            "n_signals": n_signals,
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
