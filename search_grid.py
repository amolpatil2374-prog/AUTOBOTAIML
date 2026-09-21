"""
The frozen search grid from phase2_search_plan.md — thresholds derived
from real IV/Delta data, scaled per window rather than fixed across all
windows. This is the single source of truth; phase2_search_plan.md is
the human-readable record of WHY these numbers, this file is what the
code actually runs.
"""

NIFTY_GRID = [
    # (window_minutes, threshold_pct)
    (15, 1.0), (15, 2.0), (15, 2.5), (15, 3.5),
    (60, 2.0), (60, 3.5), (60, 5.0), (60, 7.0),
    (180, 3.0), (180, 6.0), (180, 9.0), (180, 12.0),
    (375, 4.0), (375, 8.5), (375, 13.0), (375, 17.0),
    (750, 6.0), (750, 12.0), (750, 18.0), (750, 24.0),
]

CRUDEOILM_GRID = [
    (15, 1.5), (15, 2.5), (15, 4.0), (15, 5.0),
    (60, 2.5), (60, 5.0), (60, 8.0), (60, 10.0),
    (870, 10.0), (870, 20.0), (870, 30.0), (870, 40.0),
    (2610, 17.0), (2610, 34.0), (2610, 51.0), (2610, 68.0),
    (4350, 22.0), (4350, 44.0), (4350, 66.0), (4350, 88.0),
    (8700, 31.0), (8700, 62.0), (8700, 93.0), (8700, 100.0),
]

GRIDS = {"NIFTY": NIFTY_GRID, "CRUDEOILM": CRUDEOILM_GRID}

assert len(NIFTY_GRID) == 20, f"Expected 20 NIFTY combinations, got {len(NIFTY_GRID)}"
assert len(CRUDEOILM_GRID) == 24, f"Expected 24 CRUDEOILM combinations, got {len(CRUDEOILM_GRID)}"
