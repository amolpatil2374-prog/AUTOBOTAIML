"""
Computes the Tier 0 gates and Tier 1 composite score defined in the KPI
scoring framework. Two gates (G1, G2) are computable right now from data
already being collected. Three gates (G3-G5) and all of Tier 1 depend on
Phase 2 model/backtest output that doesn't exist yet — this module defines
exactly what that output needs to look like, so Phase 2 just has to write
one JSON file per symbol and this lights up automatically, no changes
needed here.

PHASE 2 CONTRACT — model_results_<SYMBOL>.json in config.DATA_DIR:
{
  "selected_strategy": {"threshold_pct": <float>, "window_minutes": <int>},
  "walk_forward": {
    "overall_win_rate": <float 0-1>,
    "ci_lower_95": <float 0-1>,        # lower bound of 95% CI on win rate
    "baseline": 0.5,
    "total_signals": <int>,
    "signals_per_fold": [<int>, ...]
  },
  "liquidity": {
    "pct_fresh_signals": <float 0-1>,  # fraction with stale_min <= 15 at signal time
    "pct_acceptable_spread": <float 0-1>
  },
  "economics": {
    "net_expectancy_pct": <float>,     # after estimated slippage, ask/bid priced
    "profit_factor": <float>,
    "breakeven_win_rate": <float 0-1>,
    "actual_win_rate": <float 0-1>
  },
  "risk": {
    "max_drawdown_pct": <float>,
    "sl_efficiency_pct": <float>,      # from MAE analysis
    "trailing_capture_pct": <float>,   # from MFE analysis
    "position_sizing_defined": <bool>
  },
  "robustness": {
    "half1_significant": <bool>,
    "half2_significant": <bool>
  }
}
"""
import json
import os

import config
import data_report

G1_THRESHOLD = 0.95
G4_MIN_SIGNALS_PER_FOLD = 30
G4_MIN_TOTAL_SIGNALS = 150
G5_MIN_FRESH_PCT = 0.70
G5_MIN_SPREAD_PCT = 0.70  # fraction of signals with acceptable spread


def compute_g1_infra_reliability():
    """Global gate, not per-symbol — same pipeline run serves both symbols."""
    log_path = os.path.join(config.LOG_DIR, "run_daily.log")
    if not os.path.exists(log_path):
        return {"gate": "G1", "status": "pending", "detail": "No run log yet."}

    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    starts = content.count("=== Daily run starting ===")
    completes = content.count("=== Daily run complete ===")
    if starts == 0:
        return {"gate": "G1", "status": "pending", "detail": "No runs recorded yet."}

    rate = completes / starts
    passed = rate >= G1_THRESHOLD
    return {
        "gate": "G1", "status": "pass" if passed else "fail",
        "detail": f"{completes}/{starts} runs completed cleanly ({rate:.0%}, need {G1_THRESHOLD:.0%})",
    }


def compute_g2_data_volume(symbol):
    stats = data_report.compute_symbol_stats(symbol)
    days = stats["trading_days"] if stats else 0
    passed = days >= config.MIN_TRADING_DAYS_FOR_TRAINING
    return {
        "gate": "G2", "status": "pass" if passed else "fail",
        "detail": f"{days}/{config.MIN_TRADING_DAYS_FOR_TRAINING} trading days collected",
    }


def _load_model_results(symbol):
    path = os.path.join(config.DATA_DIR, f"model_results_{symbol}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)


def compute_g3_statistical_significance(results):
    if results is None:
        return {"gate": "G3", "status": "pending", "detail": "Requires Phase 2 model results (not yet built)."}
    wf = results["walk_forward"]
    passed = wf["ci_lower_95"] > wf["baseline"]
    return {
        "gate": "G3", "status": "pass" if passed else "fail",
        "detail": f"CI lower bound {wf['ci_lower_95']:.1%} vs baseline {wf['baseline']:.1%}",
    }


def compute_g4_sample_size(results):
    if results is None:
        return {"gate": "G4", "status": "pending", "detail": "Requires Phase 2 model results (not yet built)."}
    wf = results["walk_forward"]
    min_fold = min(wf["signals_per_fold"]) if wf["signals_per_fold"] else 0
    passed = min_fold >= G4_MIN_SIGNALS_PER_FOLD and wf["total_signals"] >= G4_MIN_TOTAL_SIGNALS
    return {
        "gate": "G4", "status": "pass" if passed else "fail",
        "detail": f"{wf['total_signals']} total signals, smallest fold {min_fold} (need >={G4_MIN_SIGNALS_PER_FOLD}/fold, >={G4_MIN_TOTAL_SIGNALS} total)",
    }


def compute_g5_liquidity(results):
    if results is None:
        return {"gate": "G5", "status": "pending", "detail": "Requires Phase 2 model results (not yet built)."}
    liq = results["liquidity"]
    passed = liq["pct_fresh_signals"] >= G5_MIN_FRESH_PCT and liq["pct_acceptable_spread"] >= G5_MIN_SPREAD_PCT
    return {
        "gate": "G5", "status": "pass" if passed else "fail",
        "detail": f"{liq['pct_fresh_signals']:.0%} fresh quotes, {liq['pct_acceptable_spread']:.0%} acceptable spread",
    }


def _score_band(value, hi_threshold, mid_threshold, higher_is_better=True):
    """Linear-ish banding matching the framework's 100/50/0 point table."""
    if higher_is_better:
        if value >= hi_threshold:
            return 100
        if value >= mid_threshold:
            return 50 + 50 * (value - mid_threshold) / (hi_threshold - mid_threshold)
        return max(0, 50 * value / mid_threshold) if mid_threshold else 0
    else:
        if value <= hi_threshold:
            return 100
        if value <= mid_threshold:
            return 50 + 50 * (mid_threshold - value) / (mid_threshold - hi_threshold)
        return 0


def compute_tier1_score(results):
    """Only meaningful once all Tier 0 gates pass — caller enforces that."""
    wf, econ, risk, robust = results["walk_forward"], results["economics"], results["risk"], results["robustness"]

    edge = (wf["overall_win_rate"] - wf["baseline"]) * 100
    model_quality = _score_band(edge, hi_threshold=8, mid_threshold=4)

    expectancy = econ["net_expectancy_pct"]
    profit_factor = econ["profit_factor"]
    win_edge = (econ["actual_win_rate"] - econ["breakeven_win_rate"]) * 100
    economics_score = (
        _score_band(expectancy, hi_threshold=1.5, mid_threshold=0.5)
        + _score_band(profit_factor, hi_threshold=1.8, mid_threshold=1.3)
        + _score_band(win_edge, hi_threshold=8, mid_threshold=3)
    ) / 3

    dd_score = _score_band(risk["max_drawdown_pct"], hi_threshold=10, mid_threshold=20, higher_is_better=False)
    sl_score = _score_band(risk["sl_efficiency_pct"], hi_threshold=90, mid_threshold=75)
    trail_score = _score_band(risk["trailing_capture_pct"], hi_threshold=70, mid_threshold=50)
    sizing_score = 100 if risk["position_sizing_defined"] else 0
    risk_score = (dd_score + sl_score + trail_score + sizing_score) / 4

    robustness_score = 100 if (robust["half1_significant"] and robust["half2_significant"]) else \
                        50 if (robust["half1_significant"] or robust["half2_significant"]) else 0

    composite = (
        model_quality * 0.30 + economics_score * 0.30 +
        risk_score * 0.25 + robustness_score * 0.15
    )

    if composite >= 80:
        verdict = "Strong candidate"
    elif composite >= 60:
        verdict = "Promising, not there yet"
    else:
        verdict = "Not viable in current form"

    return {
        "composite": round(composite, 1), "verdict": verdict,
        "categories": {
            "Model & signal quality": round(model_quality, 1),
            "Backtest economics": round(economics_score, 1),
            "Risk management": round(risk_score, 1),
            "Regime robustness": round(robustness_score, 1),
        },
    }


def score_symbol(symbol):
    """Returns the full gate + score report for one symbol."""
    g1 = compute_g1_infra_reliability()  # global, but reported per-symbol for a single view
    g2 = compute_g2_data_volume(symbol)
    results = _load_model_results(symbol)
    g3 = compute_g3_statistical_significance(results)
    g4 = compute_g4_sample_size(results)
    g5 = compute_g5_liquidity(results)

    gates = [g1, g2, g3, g4, g5]
    all_pass = all(g["status"] == "pass" for g in gates)
    any_pending = any(g["status"] == "pending" for g in gates)

    tier1 = compute_tier1_score(results) if all_pass else None

    if all_pass:
        overall = "READY"
    elif any_pending:
        overall = "NOT READY (pending)"
    else:
        overall = "NOT READY"

    return {"symbol": symbol, "overall": overall, "gates": gates, "tier1": tier1}


if __name__ == "__main__":
    for sym in config.SYMBOLS:
        report = score_symbol(sym)
        print(f"\n{report['symbol']}: {report['overall']}")
        for g in report["gates"]:
            print(f"  {g['gate']}: {g['status']:8s} {g['detail']}")
        if report["tier1"]:
            print(f"  Tier 1 score: {report['tier1']['composite']}/100 — {report['tier1']['verdict']}")
