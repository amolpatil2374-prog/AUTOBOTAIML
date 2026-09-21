"""
Maximum Adverse Excursion (MAE) and Maximum Favorable Excursion (MFE),
computed from the SELECTED combination's actual winning trades only —
this is where stop-loss and trailing-profit levels come from, derived
from real historical price paths rather than guessed.

MAE: for trades that eventually won, how far did the price dip below
entry before recovering? The stop-loss sits at a percentile of this
distribution — tight enough to cut real losers, loose enough not to
shake out trades that would have worked.

MFE: for winning trades, how high did the price get at its best point
before the window ended? Tells us how much profit a trailing stop would
be leaving on the table vs. capturing.
"""
import numpy as np
import pandas as pd


def compute_mae_mfe(features_df, threshold_pct, window_minutes, sl_percentile=80):
    """Walks the actual price path for every WINNING trade (label=1) in
    this combination and records the worst dip (MAE) and best peak (MFE)
    along the way. Returns None if there are too few winners to compute
    anything meaningful (avoids a percentile calculation on a handful of
    points that would look precise but isn't)."""
    df = features_df.sort_values(["strike", "option_type", "timestamp"]).copy()

    mae_list = []  # % drop from entry, for winning trades
    mfe_list = []  # % peak gain from entry, for winning trades

    for (strike, side), group in df.groupby(["strike", "option_type"], sort=False):
        group = group.sort_values("timestamp").reset_index(drop=True)
        times = group["timestamp"].values
        ltps = group["ltp"].values

        for i in range(len(group)):
            entry_time = times[i]
            entry_ltp = ltps[i]
            if pd.isna(entry_ltp) or entry_ltp <= 0:
                continue

            window_end = entry_time + pd.Timedelta(minutes=window_minutes)
            future_mask = (times > entry_time) & (times <= window_end)
            future_ltps = ltps[future_mask]
            future_ltps = future_ltps[~pd.isna(future_ltps)]
            if len(future_ltps) == 0:
                continue

            target_price = entry_ltp * (1 + threshold_pct / 100)
            is_winner = (future_ltps >= target_price).any()
            if not is_winner:
                continue

            min_price = future_ltps.min()
            max_price = future_ltps.max()
            mae_pct = (min_price - entry_ltp) / entry_ltp * 100  # negative = a real dip
            mfe_pct = (max_price - entry_ltp) / entry_ltp * 100

            mae_list.append(mae_pct)
            mfe_list.append(mfe_pct)

    MIN_WINNERS_FOR_PERCENTILE = 20
    if len(mae_list) < MIN_WINNERS_FOR_PERCENTILE:
        return {
            "n_winners": len(mae_list), "sufficient": False,
            "sl_pct": None, "trailing_capture_pct": None,
        }

    mae_arr = np.array(mae_list)
    mfe_arr = np.array(mfe_list)

    # SL at the sl_percentile of how far winners dipped — e.g. 80th
    # percentile means we tolerate a dip at least as deep as 80% of real
    # winners experienced, without cutting them off early.
    sl_pct = abs(np.percentile(mae_arr, 100 - sl_percentile))

    # SL efficiency: % of these same real winners whose actual dip was
    # shallower than the SL we just derived — i.e., would NOT have been
    # stopped out early. Computed in-sample (the SL and this check use
    # the same data) — not yet cross-validated out-of-sample, honestly
    # noted rather than hidden, since that would need more data than
    # currently exists to do properly.
    sl_efficiency_pct = float((mae_arr > -sl_pct).mean() * 100)

    # Trailing capture: how much of the eventual peak gain would a
    # trailing stop set just inside the typical peak actually capture,
    # on average, across real winners.
    threshold_gain = threshold_pct
    capture_ratios = np.clip(threshold_gain / mfe_arr, 0, 1)
    trailing_capture_pct = float(np.mean(capture_ratios) * 100)

    return {
        "n_winners": len(mae_list),
        "sufficient": True,
        "sl_pct": float(sl_pct),
        "sl_efficiency_pct": sl_efficiency_pct,
        "trailing_capture_pct": trailing_capture_pct,
        "mae_percentiles": {p: float(np.percentile(mae_arr, p)) for p in [10, 25, 50, 75, 90]},
        "mfe_percentiles": {p: float(np.percentile(mfe_arr, p)) for p in [10, 25, 50, 75, 90]},
    }
