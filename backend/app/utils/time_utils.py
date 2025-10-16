"""Time utilities enforcing IST (Asia/Kolkata) as global user-visible timezone.

Functions:
  parse_user_time_ist(text: str) -> datetime | None
    Uses dateparser with TIMEZONE=Asia/Kolkata and returns naive UTC datetime for storage.

  format_ist(dt: datetime | None) -> str
    Returns 'YYYY-MM-DD HH:MM IST' or '-' if dt is None. Accepts naive UTC or aware dt.

Fallback: if zoneinfo is unavailable, manual +05:30 offset is applied.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import dateparser
from typing import Optional, Tuple

IST_ZONE_NAME = "Asia/Kolkata"

def parse_user_time_ist(text: str, prefer_future: bool = True) -> Optional[datetime]:
    if not text:
        return None
    settings = {
        "TIMEZONE": IST_ZONE_NAME,
        "TO_TIMEZONE": "UTC",
        "RETURN_AS_TIMEZONE_AWARE": True,
        "PREFER_DATES_FROM": "future" if prefer_future else "past",
    }
    dt = dateparser.parse(text, settings=settings)
    if not dt:
        return None
    # Ensure result is UTC naive for storage consistency
    return dt.astimezone(timezone.utc).replace(tzinfo=None)

def _to_aware_ist(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        return dt.astimezone(ZoneInfo(IST_ZONE_NAME))
    except Exception:
        # Manual offset fallback
        return (dt.astimezone(timezone.utc) + timedelta(hours=5, minutes=30)).replace(tzinfo=None)

def format_ist(dt: Optional[datetime]) -> str:
    if not dt:
        return "-"
    aware = _to_aware_ist(dt)
    if aware.tzinfo is None:
        # Manual fallback produced naive local time already offset
        return aware.strftime("%Y-%m-%d %H:%M IST")
    return aware.strftime("%Y-%m-%d %H:%M %Z")


def ensure_future_ist(dt_utc_naive: Optional[datetime]) -> bool:
    """Return True if the provided UTC-naive datetime is in the future when interpreted in IST.

    Accepts None and returns False. This normalizes the input as UTC (naive) and compares
    against current UTC time. Using IST conversion only for formatting consistency; the
    actual future check is reliable in UTC.
    """
    if not dt_utc_naive:
        return False
    try:
        now_utc = datetime.utcnow().replace(tzinfo=None)
        return dt_utc_naive > now_utc
    except Exception:
        return False

__all__ = ["parse_user_time_ist", "format_ist", "ensure_future_ist", "IST_ZONE_NAME"]


def parse_and_validate_ist(text: str, min_lead_seconds: int = 5) -> Tuple[datetime, str]:
    """Parse natural language time as IST, return (due_utc_naive, pretty_ist) or raise ValueError with friendly message.

    - Enforces future-only and minimum lead time in seconds
    - Stores UTC-naive for internal use; formats IST string for display/confirmation
    """
    dt_utc = parse_user_time_ist(text, prefer_future=True)
    if not dt_utc:
        raise ValueError("Sorry, I couldn't understand that time. Please try a specific time like 'today 10:30 PM' or 'in 5 minutes'.")
    now_utc = datetime.utcnow().replace(tzinfo=None)
    delta = (dt_utc - now_utc).total_seconds()
    if delta <= 0:
        raise ValueError("Scheduled time must be in the future (IST).")
    if delta < max(1, int(min_lead_seconds)):
        raise ValueError(f"Please allow at least {min_lead_seconds} seconds from now (IST).")
    return dt_utc.replace(second=0, microsecond=0), format_ist(dt_utc)
