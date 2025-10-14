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
from typing import Optional

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

__all__ = ["parse_user_time_ist", "format_ist", "IST_ZONE_NAME"]