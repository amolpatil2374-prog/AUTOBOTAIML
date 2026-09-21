# Phase 2 Search Plan — Draft for Review

This defines exactly what Phase 2 will test, before any model code gets
written. Same pattern as the KPI table: review this, freeze it, then
build against the frozen version — not the other way around.

## 1. What a "signal" means at this stage

For every fresh (non-stale) option observation already logged — one
strike, one side (CE/PE), one moment in time — ask: **if this had been
bought right then, would it have gained at least the profit threshold
within the holding window?** That's the label. This is calibration of
what "profitable" means, not yet the model choosing which ones to buy —
Phase 2's actual model learns, from features, which of these tend to be
labeled a win. The search here decides the labeling rule itself.

**Two-stage pricing, matching what the KPI framework already
requires:** the win/loss label itself uses LTP (simple, fast, fine for
calibration). Once a combination survives the gates, the actual backtest
economics (expectancy, profit factor) get *re-priced* using real ask
(buy) and bid (sell) — never LTP — exactly as the KPI framework already
specifies. Slippage-realistic numbers only matter once a candidate is
worth taking seriously.

## 2 & 3. The grid — FROZEN, properly scaled to real data [2026-09-19]

**Correction from the earlier draft:** a single fixed threshold set
applied to every window length was a real design flaw, not just a
simplification — a 15-minute hold and a 2-week hold don't have remotely
similar typical price swings. Using the same numbers for both would mean
short windows almost never hit even the smallest threshold regardless of
any real skill, while long windows might clear the largest threshold too
easily. Fixed by computing, from our own real IV and Delta data, how
much each option typically moves over each specific window, then setting
thresholds as multiples of that real expected move (0.5x = a
below-average move, 1x = average, 1.5x = above-average, 2x = a rare,
large move) — so "hard to achieve" means the same thing at every window
length, not just at one.

**NIFTY** (real IV ≈15.5%, Delta≈0.5, spot≈23,317, premium≈570 — near-ATM, Sept 2026):

| Window | Expected move | Thresholds (0.5x / 1x / 1.5x / 2x) |
|---|---|---|
| 15 min | 1.7% | 1% / 2% / 2.5% / 3.5% |
| 1 hour | 3.4% | 2% / 3.5% / 5% / 7% |
| Half-day (3 hr) | 5.9% | 3% / 6% / 9% / 12% |
| Full day (6.25 hr) | 8.5% | 4% / 8.5% / 13% / 17% |
| 2 day | 12.0% | 6% / 12% / 18% / 24% |

**CRUDEOILM** (real IV ≈55.6%, Delta≈0.555, spot≈9,195, premium≈588 — near-ATM, Sept 2026):

| Window | Expected move | Thresholds (0.5x / 1x / 1.5x / 2x) |
|---|---|---|
| 15 min | 2.6% | 1.5% / 2.5% / 4% / 5% |
| 1 hour | 5.2% | 2.5% / 5% / 8% / 10% |
| Full day (14.5 hr) | 19.6% | 10% / 20% / 30% / 40% |
| 3 day | 34.0% | 17% / 34% / 51% / 68% |
| 1 week | 43.9% | 22% / 44% / 66% / 88% |
| 2 week | 62.1% | 31% / 62% / 93% / 100% (capped — a full premium doubling is already an extreme target) |

**Total combinations: NIFTY 5 windows × 4 thresholds = 20. CRUDEOILM 6 × 4 = 24.** Same counts as the original draft, so the multiple-comparison correction below still applies exactly as designed — only the threshold *values* changed, not how many are being tested.

## 4. CE and PE — not assumed to behave the same

Calls and puts aren't assumed symmetric (skew, crash-hedging demand, and
other real effects can make them behave differently). Rather than
doubling the whole grid by running CE and PE as fully separate searches,
`option_type` becomes a real feature the model can use — and after the
main search, each surviving combination gets checked separately for
CE-only and PE-only performance as a diagnostic, to catch a combination
that looks good overall but is secretly only working for one side.

## 5. The problem this search itself creates — and the fix

Testing 20 (NIFTY) or 24 (CRUDEOILM) combinations and picking whichever
looks best is *itself* a form of the overfitting risk already discussed
— with that many tries, something will look good by chance alone, even
with zero real edge, more easily than a single test would suggest.

**Fix: a stricter significance bar that scales with how many
combinations were actually tested (a standard correction, not a new
invention).** Right now, gate G3 checks a single combination's result
against a 95% confidence interval. With N combinations tested, that
bar needs tightening to roughly 1 − (0.05⁄N) confidence to keep the
*overall* false-positive risk across all N tests where it's supposed to
be — not 95% for each individual try. For 20 combinations, that's about
99.75% confidence required per combination, not 95%. This makes the gate
meaningfully harder to pass, on purpose — that's the correction actually
working, not a bug.

**This needs a real code change to `kpi_scoring.py`'s G3 check** —
currently hardcoded to a 95% bound, needs to become aware of how many
combinations were searched. Will build this in once this plan is frozen.

## 6. Selection rule

Walk-forward evaluate every combination. Apply the corrected G3 bar
above to each. **Only combinations that clear every gate (G1-G5,
corrected G3) are eligible at all — it's entirely possible zero survive,
and that's a legitimate, honest result, not a failure to fix by loosening
anything.** Among whatever does survive, rank by the Tier 1 composite
score already defined, and report the winner(s) — never quietly picking
the "least bad" option that didn't actually clear the bar.

---

**Status: FROZEN [2026-09-19].** Grid derived from real IV/Delta data,
not picked arbitrarily. Next: build the corrected G3 significance logic
below into `kpi_scoring.py`.
