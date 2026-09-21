# KPI & Scoring Framework — Options Trading Research Project

**Applies separately to NIFTY and CRUDEOILM.** They have different liquidity
profiles and different odds of success — scoring them on one combined
number would hide that difference. Run this scorecard once per instrument.

## Design principle: gates before scores

A single weighted average lets a great number in one category paper over a
disqualifying failure in another — a strong backtest expectancy could
mathematically offset unreliable infrastructure or a statistically
meaningless edge. That defeats the purpose of dual-gate.

So this framework has two tiers:

- **Tier 0 — Hard gates.** Pass/fail, all-or-nothing. If any gate fails,
  the project's status is **NOT READY**, full stop, regardless of how good
  the Tier 1 score looks. No blending, no partial credit.
- **Tier 1 — Weighted composite score (0–100).** Only meaningful once
  every Tier 0 gate has passed. This is where genuine tradeoffs between
  categories are allowed.

---

## Tier 0 — Hard gates (all must pass)

| # | Gate | Pass condition | Why it's a gate, not a score |
|---|---|---|---|
| G1 | Infrastructure reliability | ≥95% of scheduled daily runs complete cleanly (`run_daily.log` shows `Daily run complete`, no unhandled exceptions) over the trailing 20 trading days | A great model trained on a broken pipeline's data is meaningless — this has to be true before anything else is worth measuring |
| G2 | Data volume floor | ≥20 trading days of chain data collected | The original sufficiency threshold — below this, no statistic is trustworthy regardless of what it shows |
| G3 | Statistical significance | The walk-forward win rate of the *selected* threshold/window combination has a confidence interval whose lower bound clears the naive baseline (50%) | This is the dual-gate's core purpose: distinguishes real edge from a lucky-looking number out of a multi-combination search |
| G4 | Sample size per fold | ≥30 signals generated per walk-forward fold, ≥150 signals total across all folds | A "significant" result on 12 trades isn't significant — it's noise with a p-value attached |
| G5 | Liquidity feasibility | ≥70% of backtested signals occurred on strikes with `stale_min` ≤15 at signal time, AND bid-ask spread ≤10% of premium | A backtest built on stale or wide-spread quotes overstates what's actually fillable — this is the CRUDEOILM-specific risk flagged earlier, made measurable |

**If G1–G5 all pass:** proceed to Tier 1 scoring.
**If any fail:** status is NOT READY. Report *which* gate failed and by how
much — "G3 failed, CI lower bound is 48.2%, needs 50%" is useful; "not
ready" alone is not.

---

## Tier 1 — Weighted composite score (0–100)

Only computed once Tier 0 passes. Four categories, each scored 0–100
internally, then weighted into the final number.

| Category | Weight | What it measures |
|---|---|---|
| Model & signal quality | 30% | Does the edge look real and consistent, not just present |
| Backtest economics | 30% | Is it profitable *after* realistic costs |
| Risk management | 25% | Would a real drawdown actually be survivable |
| Regime robustness | 15% | Does it hold up outside the specific period it was found in |

### Category 1 — Model & signal quality (30%)

| Metric | 100 pts | 50 pts | 0 pts |
|---|---|---|---|
| Out-of-sample edge size (win rate − 50%) | ≥8 points | 4 points | ≤1 point |
| Cross-fold consistency (std dev of per-fold win rate) | ≤3 points | 6 points | ≥10 points |
| Feature importance stability across folds | Same top 3 features in ≥80% of folds | ≥50% | <30% — signal may be noise-fitting different features each fold |

### Category 2 — Backtest economics (30%)

Prices must use ask (for entries) and bid (for exits) — never LTP or mid.
This is a hard requirement for this category to mean anything, not a
scoring choice.

| Metric | 100 pts | 50 pts | 0 pts |
|---|---|---|---|
| Net expectancy per trade (after estimated slippage) | ≥1.5% of premium | 0.5% | ≤0 — losing money net of costs |
| Profit factor (gross profit ÷ gross loss) | ≥1.8 | 1.3 | ≤1.0 |
| Actual win rate vs breakeven win rate (given option payoff asymmetry) | ≥8 points above breakeven | 3 points above | At or below breakeven |

### Category 3 — Risk management (25%)

| Metric | 100 pts | 50 pts | 0 pts |
|---|---|---|---|
| Max drawdown (% of allocated capital, backtested) | ≤10% | 20% | ≥35% |
| SL efficiency (% of eventual winners NOT stopped out early, from MAE analysis) | ≥90% | 75% | ≤50% |
| Trailing-profit capture (% of MFE-implied peak captured on winners) | ≥70% | 50% | ≤25% |
| Position sizing rule defined and capital-at-risk-per-trade capped | Fully defined, enforced in backtest | Defined, not yet enforced | Not defined |

### Category 4 — Regime robustness (15%)

| Metric | 100 pts | 50 pts | 0 pts |
|---|---|---|---|
| Performance stability across sub-periods (split accumulated days into halves, compare) | Both halves individually clear G3's significance bar | One half does | Neither does — edge may be a one-period artifact |
| Tested across more than one volatility regime (high-IV vs low-IV days, once enough data exists) | Positive expectancy in both | Positive in one | Negative in either |

---

## Reading the final score

| Score | Verdict | What it actually means |
|---|---|---|
| 80–100 | Strong candidate | Worth cautious, small-size paper trading — not worth skipping straight to live capital |
| 60–79 | Promising, not there yet | Real signal present, but at least one category (usually economics or robustness) needs more data or refinement |
| Below 60 | Not viable in current form | Either no real edge, or one that costs/risk/regime sensitivity would erode in practice |

**Passing Tier 0 but scoring low in Tier 1 is a genuinely useful, honest
outcome** — it means "there's a statistically real pattern, but it's not
economically good enough to trade." That's different from, and more
informative than, "not enough data yet." Don't be discouraged by a low
Tier 1 score after passing Tier 0 gates — it's the system doing its job.

---

## Practical notes

- **Recompute this scorecard on every model retrain**, not once. A score
  can degrade as new data comes in just as easily as it can improve —
  this is a live health check, not a one-time certification.
- **Score NIFTY and CRUDEOILM independently.** Given CRUDEOILM's already-
  observed liquidity issues, expect it may struggle to clear G5 even if
  its raw statistics look fine — that's the gate doing exactly what it's
  for.
- **A gate failing is data, not a setback.** "G3 hasn't passed after 40
  trading days" is a legitimate, useful finding — it may mean this
  instrument/timeframe combination doesn't have a tradeable edge at this
  infrastructure tier, which is worth knowing before risking capital, not
  a reason to loosen the gate until it passes.
