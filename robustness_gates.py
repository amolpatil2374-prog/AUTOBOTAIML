"""
Item #12 from the external review, built into OUR real codebase against
OUR real data — not merged from the foreign zip that review was about.

Two checks that "half1/half2 significant" (already built) doesn't cover:

1. Single-day profit concentration: a strategy that only "works" because
   of one extreme day isn't a real, repeatable edge — it's one lucky
   trade wearing a statistics costume. Checks what share of TOTAL profit
   came from the single best day.

2. Slippage stress test: our economics already use real historical
   ask/bid, not LTP — but real-world spreads can be worse than what got
   observed historically. Recomputes expectancy assuming the spread was
   1.5x and 2x wider than what was actually seen, to check the edge
   isn't razor-thin and dependent on unusually good historical fills.
"""
import pandas as pd


def single_day_concentration(trades):
    """trades: the raw per-trade list from economics.compute_economics()
    (needs the "trades" key, not just the aggregate stats).
    Returns the max % of total profit contributed by any single day —
    only meaningful when total profit is actually positive; a strategy
    that's net-losing doesn't have a "concentration of profit" in the
    same sense."""
    if not trades:
        return {"sufficient": False}

    df = pd.DataFrame(trades)
    daily_pnl = df.groupby("date")["return_pct"].sum()

    total_profit = daily_pnl[daily_pnl > 0].sum()  # only days that were net positive
    if total_profit <= 0:
        return {"sufficient": True, "max_single_day_share_pct": None, "reason": "no net positive days to concentrate"}

    max_day_profit = daily_pnl.max()
    share_pct = (max_day_profit / total_profit * 100) if max_day_profit > 0 else 0.0

    return {
        "sufficient": True,
        "max_single_day_share_pct": float(share_pct),
        "n_days_with_trades": int(daily_pnl.shape[0]),
        "best_day_pnl_pct": float(max_day_profit),
    }


def slippage_stress_test(trades, stress_multipliers=(1.5, 2.0)):
    """Recomputes net expectancy assuming the entry/exit spread was
    stress_multiplier times wider than what was actually observed at
    entry. Splits the extra cost evenly between entry (worse ask) and
    exit (worse bid) — a standard, defensible way to simulate worse
    real-world fills without needing more data than we have."""
    if not trades:
        return {"sufficient": False}

    usable = [t for t in trades if t.get("entry_bid") is not None]
    if len(usable) < 20:
        return {"sufficient": False, "reason": f"only {len(usable)} trades have a real entry bid to stress"}

    results = {}
    for mult in stress_multipliers:
        stressed_returns = []
        for t in usable:
            observed_spread = t["entry_ask"] - t["entry_bid"]
            extra_half_spread = observed_spread / 2 * (mult - 1)
            stressed_entry_ask = t["entry_ask"] + extra_half_spread
            stressed_exit_bid = t["exit_bid"] - extra_half_spread
            if stressed_entry_ask <= 0:
                continue
            stressed_return_pct = (stressed_exit_bid - stressed_entry_ask) / stressed_entry_ask * 100
            stressed_returns.append(stressed_return_pct)

        if not stressed_returns:
            results[f"{mult}x"] = None
            continue
        avg = sum(stressed_returns) / len(stressed_returns)
        results[f"{mult}x"] = float(avg)

    baseline_expectancy = sum(t["return_pct"] for t in usable) / len(usable)

    return {
        "sufficient": True,
        "n_trades_stressed": len(usable),
        "baseline_expectancy_pct": float(baseline_expectancy),
        "stressed_expectancy_pct": results,
        "survives_2x_stress": results.get("2.0x") is not None and results["2.0x"] > 0,
    }
