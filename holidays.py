"""
Exchange holiday calendars, used to correctly exclude real holidays from
the trading-day count — a holiday that falls on a weekday currently gets
logged all day (with frozen, repeated prices) and would otherwise be
wrongly counted as a valid trading day toward the 20-day floor.

NSE_HOLIDAYS_2026 — VERIFIED, straight from NSE's own official circular
(NSE/CMTR/71775, dated December 12, 2025, "Trading holidays for the
calendar year 2026"). Source: https://nsearchives.nseindia.com/content/circulars/CMTR71775.pdf

MCX_HOLIDAYS_2026 — VERIFIED, from MCX's own official holiday page
(provided directly by the user, checked at mcxindia.com). Split into two
groups, because MCX holidays are NOT all the same shape:

  - MCX_FULL_HOLIDAYS_2026: both morning and evening sessions closed —
    genuinely no trading all day, safe to exclude the whole day.
  - MCX_PARTIAL_HOLIDAYS_2026: only the morning session is closed; the
    evening session (5:00 PM onward) trades normally. Excluding these
    days entirely would throw away real, valid evening-session data —
    so these are NOT excluded from the day count. Flagged separately so
    this is a visible, deliberate choice, not something silently missed.

  New Year's Day (Jan 1) is the one reversed case — morning open,
  evening closed. Also not excluded at the day level for the same
  reason (real morning data exists that day).
"""

NSE_HOLIDAYS_2026 = {
    "2026-01-26",  # Republic Day
    "2026-03-03",  # Holi
    "2026-03-26",  # Shri Ram Navami
    "2026-03-31",  # Shri Mahavir Jayanti
    "2026-04-03",  # Good Friday
    "2026-04-14",  # Dr. Baba Saheb Ambedkar Jayanti
    "2026-05-01",  # Maharashtra Day
    "2026-05-28",  # Bakri Id
    "2026-06-26",  # Muharram
    "2026-09-14",  # Ganesh Chaturthi
    "2026-10-02",  # Mahatma Gandhi Jayanti
    "2026-10-20",  # Dussehra
    "2026-11-10",  # Diwali-Balipratipada
    "2026-11-24",  # Prakash Gurpurb Sri Guru Nanak Dev
    "2026-12-25",  # Christmas
}

# Both sessions closed — safe to exclude the whole day from CRUDEOILM's count.
MCX_FULL_HOLIDAYS_2026 = {
    "2026-01-26",  # Republic Day
    "2026-04-03",  # Good Friday
    "2026-10-02",  # Mahatma Gandhi Jayanti
    "2026-12-25",  # Christmas
}

# Morning closed, evening open — real trading data still exists that day,
# so NOT excluded from the day count. Kept here for visibility/reference.
MCX_PARTIAL_HOLIDAYS_2026 = {
    "2026-03-03",  # Holi
    "2026-03-26",  # Shri Ram Navami
    "2026-03-31",  # Shri Mahavir Jayanti
    "2026-04-14",  # Dr. Baba Saheb Ambedkar Jayanti
    "2026-05-01",  # Maharashtra Day
    "2026-05-28",  # Bakri Id
    "2026-06-26",  # Moharram
    "2026-09-14",  # Ganesh Chaturthi
    "2026-10-20",  # Dassera
    "2026-11-10",  # Diwali-Balipratipada
    "2026-11-24",  # Guru Nanak Jayanti
}

# Reversed case — morning open, evening closed. Not excluded, same reasoning.
MCX_REVERSED_DAYS_2026 = {
    "2026-01-01",  # New Year Day
}


def is_holiday(symbol, date_str):
    """date_str in 'YYYY-MM-DD' format. Returns True only for days where
    the WHOLE trading window is genuinely closed — a day with a live
    partial session (most MCX holidays) is correctly NOT flagged here,
    since real, valid data exists for part of that day."""
    if symbol == "NIFTY":
        return date_str in NSE_HOLIDAYS_2026
    if symbol == "CRUDEOILM":
        return date_str in MCX_FULL_HOLIDAYS_2026
    return False
