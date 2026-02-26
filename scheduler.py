"""
Scheduler — computes scheduled_time for LATER decisions.
"""

from datetime import datetime, timedelta, timezone
from config import (
    QUIET_HOUR_START, QUIET_HOUR_END, QUIET_RESUME_HOUR,
    BASE_BACKOFF_MINUTES, DEFAULT_WORKING_HOUR,
)


def compute_scheduled_time(event: dict, explanation_code: str,
                           frequency_count: int = 0) -> str | None:
    """
    Compute the scheduled_time for a LATER decision.
    Returns ISO-8601 string or None.

    Logic:
    - Quiet hours → schedule at QUIET_RESUME_HOUR next day
    - Frequency limit → exponential backoff
    - Reminder → next working hour
    - Default → +15 minutes
    """
    ts = event.get("parsed_timestamp", datetime.now(timezone.utc))
    expires_at = event.get("expires_at")

    scheduled = None

    if explanation_code == "RULE_OVERRIDE":
        # Check if downgraded due to quiet hours
        hour = ts.hour
        if _is_quiet_hour(hour):
            scheduled = _next_morning(ts)
        else:
            scheduled = ts + timedelta(minutes=15)

    elif explanation_code == "FREQUENCY_LIMIT":
        # Exponential backoff based on how many events sent recently
        backoff = BASE_BACKOFF_MINUTES * max(1, frequency_count - 3)
        scheduled = ts + timedelta(minutes=backoff)

    elif event.get("event_type") == "reminder":
        # Schedule at next working hour
        scheduled = _next_working_hour(ts)

    else:
        # Default: 15 minutes delay
        scheduled = ts + timedelta(minutes=15)

    # Check expiration
    if expires_at and scheduled and scheduled > expires_at:
        return "EXPIRED"

    return scheduled.isoformat() if scheduled else None


def _is_quiet_hour(hour: int) -> bool:
    """Check if the hour falls within quiet hours."""
    if QUIET_HOUR_START > QUIET_HOUR_END:
        return hour >= QUIET_HOUR_START or hour < QUIET_HOUR_END
    return QUIET_HOUR_START <= hour < QUIET_HOUR_END


def _next_morning(ts: datetime) -> datetime:
    """Return next day at QUIET_RESUME_HOUR."""
    next_day = ts + timedelta(days=1)
    return next_day.replace(hour=QUIET_RESUME_HOUR, minute=0, second=0, microsecond=0)


def _next_working_hour(ts: datetime) -> datetime:
    """Return next occurrence of DEFAULT_WORKING_HOUR."""
    if ts.hour < DEFAULT_WORKING_HOUR:
        return ts.replace(hour=DEFAULT_WORKING_HOUR, minute=0, second=0, microsecond=0)
    else:
        next_day = ts + timedelta(days=1)
        return next_day.replace(hour=DEFAULT_WORKING_HOUR, minute=0, second=0, microsecond=0)
