# Modification List — Options Trading Project

Every change or addition requested, plus every open item found during
review. Each item is marked with a status, so nothing gets lost or
forgotten. New items always get added at the bottom with the date.

**Status meaning:**
- 🟢 **DOABLE NOW** — can be done any time, does not need to wait
- 🟡 **NEEDS RESEARCH** — needs checking a fact somewhere, not data-dependent, can be done any time
- 🔴 **NEEDS MORE DATA** — must wait for enough real trading days to build up
- 🔵 **FUTURE PHASE** — depends on an earlier phase being finished first

---

## 1. Strategy KPI comparison table
🟢 **DONE — Design frozen [2026-09-13]**
One row per tested strategy. Full column list agreed. Will be recorded in
a Google Sheet, with a link shown on the dashboard, instead of a wide
table inside the website itself.

## 2. Check CRUDEOILM strike price gap from real data — DONE [2026-09-19]
🟢 **DONE — confirmed correct with real data**
Checked all 207 real strikes actually collected. Every single gap
between consecutive strikes is exactly 50, no exceptions. The original
assumption was correct — now a verified fact instead of a guess, no
code change needed.

## 3. Check if MCX CRUDEOILM options allow early exercise — DONE [2026-09-19]
🟢 **DONE — confirmed correct, strong sourcing**
Confirmed from MCX's own official circular (MCX/TRD/177/2018, about
crude oil options specifically): "European Style options, which can be
devolved only on the day of Expiry." Backed independently by four other
sources too. Our existing math (Black-76, European-style) was already
correct — no code change needed.
One related detail, not a fix: unclosed ITM options at expiry convert
into a real futures position automatically ("devolvement"), rather than
a cash settlement — a settlement-mechanics detail, doesn't affect the
Greeks math itself.

## 4. Add a real exchange holiday calendar
🟢 **DOABLE NOW**
The system currently assumes every weekday is a trading day. Needs a
real NSE + MCX holiday list added to the code.

## 5. Make MCX evening close time date-aware
🟢 **DOABLE NOW**
Currently fixed at 23:30 all year. Real close time shifts to 23:55 during
part of the year. This is a code fix, not dependent on data.

## 6. Review KPI scoring cutoffs using real results
🔴 **NEEDS MORE DATA**
Current cutoffs (like "profit factor above 1.8 = full score") are
general industry rules of thumb. Can only be properly checked once
several real strategies have been tested in Phase 2.
**When:** after Phase 2 has produced real backtest results for a few
different strategies.

## 7. Risk-free interest rate — DECIDED [2026-09-19]: manual periodic check, not automated
🟢 **DONE — decision made, value updated**
Measured the real impact first: even across a wide realistic rate range
(5%-8%), IV moved by well under 0.1 percentage points — genuinely
negligible for the short-dated options we log. Looked for a free,
reliable API to automate this — none found; RBI/FBIL only publish this
on their own websites, not through a stable public API, so automating
would mean a fragile scraper for a number that barely matters.
**Decision: left as a manual constant, updated periodically (every few
months) rather than automated.** Updated to the real current value found
(5.26%, from the real 91-day T-bill yield, Sept 2026), replacing the old
6.5% guess. Update the `RISK_FREE_RATE` constant in Code.gs the next
time you think of it — no urgency, low impact either way.

## 8. Phase 2 — Feature engineering + first-cut ML model
🔴 **NEEDS MORE DATA**
**When:** after 20 trading days minimum are collected (currently
in progress, being monitored).

## 9. Phase 3 — Strategy backtest engine + buy/sell signal generation with SL and trailing profit
🔵 **FUTURE PHASE**
**When:** after Phase 2 is built and shows real, statistically-checked
results (passes the dual-gate).

## 10. Phase 4 — Paper P&L tracking (test results without real money)
🔵 **FUTURE PHASE**
**When:** after Phase 3 is built.

## 11. Position sizing / capital-at-risk rules
🔵 **FUTURE PHASE — not yet designed at all**
Currently a completely empty gap — no rules exist yet for how much money
to risk per trade. Should be designed alongside Phase 3 or 4, not left
until the very end.

## 12. Search plan for Phase 2 — DONE [2026-09-19]
🟢 **DONE — frozen, grounded in real data, G3 correction built and verified**
44 total combinations (20 NIFTY, 24 CRUDEOILM). Thresholds derived from
real IV/Delta data (each window's actual typical option move), not
picked arbitrarily — see `phase2_search_plan.md`. Built and verified the
matching G3 correction in `kpi_scoring.py`: a proper Wilson score
interval (checked exactly against `statsmodels`' trusted implementation)
with a multiple-comparison correction that tightens automatically based
on how many combinations get tested — confirmed with a real case where
the old check would have wrongly passed a result the corrected one
correctly fails.
**Remaining:** building it and running it still needs real data (item 8).

## 13. Add bid/ask size (quantity), not just price, to the option chain log
🟢 **DOABLE NOW — optional, not yet requested**
Currently only bid/ask price is logged, not how much quantity sits at
that price. Easy to add if wanted later.

## 14. Add whole-chain PCR (currently only calculated for the logged strike range)
🟢 **DOABLE NOW — optional, not yet requested**

## 15. Check if Angel One has a separate official Greeks/IV API
🟡 **NEEDS RESEARCH — optional**
Currently Greeks/IV are calculated ourselves (Black-76 method, already
tested and verified). Checking if Angel One has their own official
numbers could be used as a cross-check later, but is not required — our
own calculation already works correctly.

## 16. Add India VIX to the dashboard for extra market context
🟢 **DOABLE NOW — optional, not yet requested**

## 17. Clean up the repo — remove unnecessary AUTOBOTAIMLGIT.zip file
🟢 **DOABLE NOW — simple cleanup**

## 18. Confirm no duplicate/confusing leftover files in the GitHub repo (old dashboard.html/index.html copies)
🟢 **DOABLE NOW — quick check**

## 19. Turn off the Windows Task Scheduler tasks, now that GitHub Actions is working
🟢 **DOABLE NOW — whenever you feel confident**
Not urgent — both can safely run side by side for a while as extra
safety, until you fully trust the GitHub Actions version.

## 20. NIFTY IV/Greeks showing blank — real cause found, fix identified
🟡 **NEEDS CODE FIX — cause understood from real data, not fully proven**
First check (2026-09-14) was a false alarm — that day was Ganesh
Chaturthi, a genuine NSE holiday, so "stale since Friday" was correct
behavior, not a bug.

Checked today instead (2026-09-15, a real trading day) — staleness is
correctly fresh (0-4 minutes), but IV is still blank, 0% all day. Real
cause found: **today is the exact expiry date of these options** (the
`expiry` column confirms it). With only hours left before expiry, these
options have almost no time value left — a well-known hard case for this
kind of math generally, not unique to us. Re-ran the real numbers
ourselves and saw the solver take a wild, shaky first step in this
condition, though it did eventually recover in that one test case.

## 20. NIFTY IV/Greeks showing blank on expiry day — CONFIRMED RESOLVED [2026-09-19]
🟢 **DONE — confirmed with real data, no code change needed**
Checked fresh data from Sept 16, 17, 18 (normal, non-expiry days): IV is
present 97-99.9% of the time for NIFTY. This confirms the cause really
was the near-zero-time-to-expiry math edge case, and it fully resolves
itself on any normal day, on its own, with no code change required.

## 21. Strange NIFTY bid/ask numbers — CONFIRMED FALSE ALARM [2026-09-19]
🟢 **DONE — was Claude's own mistake, not a real data problem**
Re-checked using the correct column positions (the original check used
wrong column numbers by mistake). With the correct columns, bid/ask
values are completely healthy — zero suspicious rows out of 9,800
checked. No real issue ever existed here.

## 22. Holiday calendar — DONE [2026-09-19]
🟢 **DONE — built and tested with real, verified data from both exchanges**
NSE list verified from NSE's own official circular. MCX list provided
directly by you from MCX's own site. Correctly handles MCX's split
sessions — only the 4 true full-closure days (Republic Day, Good Friday,
Gandhi Jayanti, Christmas) are excluded from the count; the 11
partial-holiday days (morning closed, evening open) are correctly kept,
since real trading data exists in the evening session on those days.
Tested against both a full-closure day and a partial-holiday day to
confirm each is handled correctly.

**One known, accepted limitation, not fixed:** on a partial-holiday
morning, that portion of the day still logs frozen prices (same issue as
before, just limited to part of one day instead of the whole day). Not
fixed for now since the impact is much smaller — a few frozen hours
mixed into an otherwise-valid day, not a whole day miscounted. Worth
revisiting only if it turns out to matter once real model training
starts.





