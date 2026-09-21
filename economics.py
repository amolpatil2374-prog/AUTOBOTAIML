"""
Realistic backtest economics for the SELECTED combination — buys priced
at the real ASK (what you'd actually pay), sells priced at the real BID
(what you'd actually receive), never LTP. This is the one place a
backtest most commonly lies to itself by assuming free, instant fills at
the last traded price.
"""
import pandas as pd


def compute_economics(features_df, threshold_pct, window_minutes):
    """For every observation with a real ask/bid available, simulates:
    buy at ask, and either sell at bid once the LTP-based threshold is
    hit (a real winner) or sell at bid at window end (a real loser or a
    breakeven-ish exit). Returns None if too few trades exist to report
    anything meaningful."""
    df = features_df.sort_values(["strike", "option_type", "timestamp"]).copy()

    trade_returns_pct = []

    for (strike, side), group in df.groupby(["strike", "option_type"], sort=False):
        group = group.sort_values("timestamp").reset_index(drop=True)
        times = group["timestamp"].values
        ltps = group["ltp"].values
        asks = group["ask"].values
        bids = group["bid"].values

        for i in range(len(group)):
            entry_time = times[i]
            entry_ask = asks[i]
            entry_ltp = ltps[i]
            if pd.isna(entry_ask) or entry_ask <= 0 or pd.isna(entry_ltp) or entry_ltp <= 0:
                continue

            window_end = entry_time + pd.Timedelta(minutes=window_minutes)
            future_mask = (times > entry_time) & (times <= window_end)
            future_ltps = ltps[future_mask]
            future_bids = bids[future_mask]
            valid = ~pd.isna(future_ltps) & ~pd.isna(future_bids) & (future_bids > 0)
            future_ltps, future_bids = future_ltps[valid], future_bids[valid]
            if len(future_ltps) == 0:
                continue

            target_price = entry_ltp * (1 + threshold_pct / 100)
            hit_mask = future_ltps >= target_price
            if hit_mask.any():
                exit_bid = future_bids[hit_mask][0]  # sell at the first moment threshold is hit
            else:
                exit_bid = future_bids[-1]  # window ended — exit at the last available real bid

            trade_return_pct = (exit_bid - entry_ask) / entry_ask * 100  # real, slippage-inclusive return
            trade_returns_pct.append(trade_return_pct)

    MIN_TRADES = 20
    if len(trade_returns_pct) < MIN_TRADES:
        return {"n_trades": len(trade_returns_pct), "sufficient": False}

    import numpy as np
    returns = np.array(trade_returns_pct)
    wins = returns[returns > 0]
    losses = returns[returns <= 0]

    gross_profit = wins.sum() if len(wins) else 0.0
    gross_loss = abs(losses.sum()) if len(losses) else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None

    return {
        "n_trades": len(trade_returns_pct),
        "sufficient": True,
        "net_expectancy_pct": float(returns.mean()),
        "actual_win_rate": float((returns > 0).mean()),
        "profit_factor": profit_factor,
        "breakeven_win_rate": _breakeven_win_rate(wins, losses),
    }


def _breakeven_win_rate(wins, losses):
    """The minimum win rate needed to break even, given the real average
    win size and average loss size actually observed."""
    if len(wins) == 0 or len(losses) == 0:
        return None
    avg_win = wins.mean()
    avg_loss = abs(losses.mean())
    if (avg_win + avg_loss) == 0:
        return None
    return float(avg_loss / (avg_win + avg_loss))
