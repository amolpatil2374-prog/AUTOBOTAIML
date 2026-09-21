# KPI Target Analysis — Are They Correct, Are They Sufficient, Where From

Straight answer to the question: **most of these numbers were picked by
me as reasonable-sounding round numbers, not derived from real analysis
specific to this project.** Some can be properly checked or computed
right now without waiting for more data — done below. Others genuinely
cannot be fixed without real strategy results existing first.

---

## G1 — Infrastructure reliability (≥95%)

**Where from:** A generic engineering convention (95%/99% uptime-style
numbers are common SLA choices), not derived from anything specific to
this project.

**Can it be checked now?** Not really — we don't have enough real daily
run history yet to know if 95% is easy, hard, or about right for this
specific pipeline. Most of tonight's failures happened during active
development/testing, not during real unattended operation.

**Verdict: unverified, but low-stakes.** A wrong number here just means
the gate is slightly too strict or too loose about infra health — it
doesn't corrupt any actual trading conclusion the way a wrong G3/G4
would. Leaving as-is for now; worth revisiting once a few real weeks of
unattended running have passed.

## G2 — Minimum 20 trading days

**Where from:** Picked as "roughly a month of trading days" — an
intuitive round number, not a calculated one. No power analysis, no
study of how much history this specific model/feature setup actually
needs.

**Can it be checked now? Not fully** — this is fundamentally about
whether 20 days' worth of *feature diversity* (different market
conditions) is enough, which can't be answered by math alone; it needs
real experience. **Verdict: acknowledged weak point, genuinely needs
more data before it can be validated either way.**

## G3 — Statistical significance (Wilson + multiple-comparison correction)

**Where from:** The *method* is a real, standard, verified statistical
technique (Wilson score interval, Bonferroni correction) — not arbitrary.
The base 95% confidence level before correction is a conventional
choice, not derived specifically for this project, but it's the
standard default across science and industry for good reason.

**Verdict: sound.** This is the one gate built on real methodology, not
a guess.

## G4 — Sample size (≥30/fold, ≥150 total) — **REAL PROBLEM FOUND**

**Where from:** Picked as "reasonable-sounding minimums," no power
analysis behind them.

**Checked properly, right now, with real math:** ran a formal
statistical power analysis — how many real signals are actually needed
to reliably detect a genuine edge, given our own corrected significance
level from G3. Results: to reliably detect even a generous 8-point edge
(58% win rate) at 80% power, roughly **500 signals** are needed — not
150. To detect a smaller but still economically meaningful 3-point edge,
over **3,600** are needed.

**Verdict: the current number is genuinely, provably too low — this
isn't a judgment call, it's a computed fact.** Fixed below.

## G5 — Liquidity (≥70% fresh, ≥70% acceptable spread)

**Where from:** Picked as "reasonable-sounding," no real data behind it
when first set.

**Checked against real data now:** the actual Phase 2 test run against
real NIFTY data showed **100%** fresh quotes and **100%** acceptable
spread for the selected combination — comfortably clearing 70% with
huge room to spare. **But this is only one data point**, near-ATM NIFTY
specifically. CRUDEOILM showed meaningfully worse IV/data presence
earlier this session (30-34%), suggesting its real liquidity picture
could look very different. **Verdict: looks generous for NIFTY, unknown
for CRUDEOILM — needs checking against real CRUDEOILM signal data once
it exists, not assumed to be the same.**

## Tier 1 scoring bands (economics, risk, model-quality point cutoffs)

**Where from:** General trading/quant industry rules of thumb (a profit
factor above 1.5-2 being "good" is a commonly cited convention), not
derived from this project's own real strategy results.

**Can this be checked now? No — genuinely not possible yet.** There's no
way to know what "good" looks like for *this specific system's* real
cost structure and constraints without real strategy results to compare
against. **Verdict: honestly unverifiable until real strategies exist**
— already tracked as Modification List item #6, correctly marked as
needing real data, not something to fix by guessing harder.

---

## Fixing G4 now — the one with a real, computed answer

Replacing the flat 150-signal minimum with a properly derived
requirement: enough signals to reliably detect a 5-point edge (a
reasonably meaningful, not-too-generous target) at 80% power, computed
fresh from however many combinations actually got tested — scaling
correctly the same way G3 already does, rather than staying a fixed
number regardless of search width.
