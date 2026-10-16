"""Calendar arithmetic for repeats and cycles. No dependency beyond the
standard library: a month step lands on the same day of the month, or the
last day when the month is shorter (Jan 31 + 1 month = Feb 28/29)."""

import calendar
from datetime import date, timedelta


def add_interval(start, every, unit):
    if unit == "day":
        return start + timedelta(days=every)
    if unit == "week":
        return start + timedelta(weeks=every)
    if unit in ("month", "year"):
        months = every * (12 if unit == "year" else 1)
        y, m = divmod(start.month - 1 + months, 12)
        year, month = start.year + y, m + 1
        return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))
    raise ValueError(f"unknown repeat unit: {unit}")
