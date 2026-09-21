"""
Runs the full frozen search grid for one symbol: for every (window,
threshold) combination, builds labels, walk-forward evaluates a simple
logistic regression, and — using the SAME Wilson-lower-bound statistic
kpi_scoring.py's G3 gate uses, with the SAME multiple-comparison
correction — selects whichever combination has the strongest genuine
statistical case, not just the highest raw number.

Writes model_results_<SYMBOL>.json matching the contract documented in
kpi_scoring.py. That file is ALL kpi_scoring.py needs to light up G3-G5
and Tier 1 automatically — this script's only job is producing it
correctly.
"""
import json
import logging
import os

import config
import feature_engineering as fe
import label_construction as lc
import walk_forward as wf
import risk_analysis as ra
import economics as ec
import search_grid
import kpi_scoring
from logging_setup import get_logger

log = get_logger("train_model", "train_model.log")

MIN_SIGNALS_TO_ATTEMPT = 10  # below this, don't even bother scoring a combination


def run_for_symbol(symbol):
    log.info(f"=== {symbol}: starting Phase 2 search ===")
    grid = search_grid.GRIDS[symbol]
    n_combinations = len(grid)

    features = fe.build_features(symbol)
    if features is None:
        log.info(f"{symbol}: no chain data yet — skipping entirely.")
        return

    candidates = []
    for window_minutes, threshold_pct in grid:
        labeled = lc.label_combination(features, threshold_pct, window_minutes)
        result = wf.walk_forward_evaluate(labeled)

        if result["total_signals"] < MIN_SIGNALS_TO_ATTEMPT:
            log.info(f"  window={window_minutes}min threshold={threshold_pct}% -> only {result['total_signals']} signals, skipping (need >={MIN_SIGNALS_TO_ATTEMPT})")
            continue

        conf = kpi_scoring.required_confidence(n_combinations)
        lower_bound = kpi_scoring.wilson_lower_bound(result["overall_win_rate"], result["total_signals"], conf)
        log.info(f"  window={window_minutes}min threshold={threshold_pct}% -> {result['total_signals']} signals, "
                  f"win_rate={result['overall_win_rate']:.1%}, Wilson lower bound={lower_bound:.1%} (at {conf:.2%} confidence)")

        candidates.append({
            "window_minutes": window_minutes, "threshold_pct": threshold_pct,
            "walk_forward": result, "wilson_lower_bound": lower_bound, "labeled": labeled,
        })

    if not candidates:
        log.info(f"{symbol}: no combination had enough signals to even attempt scoring. Writing no results file — dashboard will correctly show 'pending'.")
        return

    # Select by Wilson lower bound, not raw win rate — this is what actually
    # accounts for sample size and the multiple-comparison correction, so
    # the "best" pick is the one with the strongest real statistical case,
    # not just the luckiest-looking number.
    best = max(candidates, key=lambda c: c["wilson_lower_bound"])
    log.info(f"{symbol}: selected window={best['window_minutes']}min threshold={best['threshold_pct']}% "
              f"(Wilson lower bound {best['wilson_lower_bound']:.1%})")

    # IMPORTANT: everything below uses the model's ACTUAL out-of-sample
    # buy-signals (signal_rows), never the full labeled dataset. Buying
    # "everything that got labeled" and buying "what the model actually
    # signals" are different populations with different real economics —
    # conflating them was a real bug caught by checking output carefully,
    # not something to repeat here.
    signal_rows = best["walk_forward"]["signal_rows"]

    risk = ra.compute_mae_mfe(signal_rows, best["threshold_pct"], best["window_minutes"])
    econ = ec.compute_economics(signal_rows, best["threshold_pct"], best["window_minutes"])

    # Liquidity check: fraction of the model's ACTUAL signals that were
    # fresh (stale_min <= 15) and had an acceptable spread at signal time.
    fresh = (signal_rows["stale_min"] <= 15).mean() if len(signal_rows) else 0.0
    acceptable_spread = (signal_rows["spread_pct"] <= 0.10).mean() if len(signal_rows) else 0.0

    # Robustness: split the model's actual signal-days into two halves,
    # check each half's precision independently clears the same
    # significance bar on its own — same population as everything else
    # here, not the raw labeled data.
    labeled_only = signal_rows.copy()
    labeled_only["trade_date"] = labeled_only["timestamp"].dt.date
    days = sorted(labeled_only["trade_date"].unique())
    mid = len(days) // 2
    half1_days, half2_days = set(days[:mid]), set(days[mid:])

    def half_significant(day_set):
        subset = labeled_only[labeled_only["trade_date"].isin(day_set)]
        if len(subset) < MIN_SIGNALS_TO_ATTEMPT:
            return False
        wr = subset["label"].mean()
        lb = kpi_scoring.wilson_lower_bound(wr, len(subset), kpi_scoring.required_confidence(n_combinations))
        return bool(lb > 0.5)

    robustness = {
        "half1_significant": half_significant(half1_days) if mid > 0 else False,
        "half2_significant": half_significant(half2_days) if mid > 0 else False,
    }

    results = {
        "combinations_tested": n_combinations,
        "selected_strategy": {"threshold_pct": best["threshold_pct"], "window_minutes": best["window_minutes"]},
        "walk_forward": {
            "overall_win_rate": best["walk_forward"]["overall_win_rate"],
            "total_signals": best["walk_forward"]["total_signals"],
            "baseline": 0.5,
            "signals_per_fold": best["walk_forward"]["signals_per_fold"],
        },
        "liquidity": {
            "pct_fresh_signals": float(fresh),
            "pct_acceptable_spread": float(acceptable_spread),
        },
        "economics": econ if econ.get("sufficient") else {
            "net_expectancy_pct": None, "profit_factor": None,
            "breakeven_win_rate": None, "actual_win_rate": None,
        },
        "risk": {
            "max_drawdown_pct": None,  # needs a full equity-curve simulation — not yet built, honestly left blank
            "sl_efficiency_pct": risk.get("sl_efficiency_pct") if risk.get("sufficient") else None,
            "trailing_capture_pct": risk.get("trailing_capture_pct") if risk.get("sufficient") else None,
            "position_sizing_defined": False,  # Modification List item 11 — genuinely not designed yet
        },
        "robustness": robustness,
    }

    os.makedirs(config.DATA_DIR, exist_ok=True)
    out_path = os.path.join(config.DATA_DIR, f"model_results_{symbol}.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    log.info(f"{symbol}: wrote {out_path}")


def main():
    for symbol in config.SYMBOLS:
        try:
            run_for_symbol(symbol)
        except Exception as e:
            log.error(f"{symbol}: Phase 2 search failed: {e}")


if __name__ == "__main__":
    main()
