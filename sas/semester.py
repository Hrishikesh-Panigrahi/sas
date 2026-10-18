"""The current teaching semester's end date.

Set SEMESTER_END (YYYY-MM-DD) in the environment for the real date. Without it,
the odd semester is assumed to end on 30 November and the even one on 30 April.
"""
import datetime

from django.conf import settings
from django.utils import timezone


def semester_end(today=None):
    today = today or timezone.localdate()
    if settings.SEMESTER_END:
        try:
            end = datetime.date.fromisoformat(settings.SEMESTER_END)
            if end >= today:
                return end
        except ValueError:
            pass
    if today.month >= 7:
        return datetime.date(today.year, 11, 30)
    if today.month <= 4:
        return datetime.date(today.year, 4, 30)
    return datetime.date(today.year, 11, 30)   # May/June: the next odd semester


def weeks_left(today=None):
    """Teaching weeks remaining after today (0 once the semester is over)."""
    today = today or timezone.localdate()
    days = (semester_end(today) - today).days
    return max(0.0, days / 7.0)
