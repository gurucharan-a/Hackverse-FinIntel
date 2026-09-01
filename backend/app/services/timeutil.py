from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import TZ_NAME

IST = ZoneInfo(TZ_NAME)


def now_ist() -> datetime:
    return datetime.now(IST)


def iso_ist(dt: datetime | None = None) -> str:
    d = dt or now_ist()
    if d.tzinfo is None:
        d = d.replace(tzinfo=IST)
    return d.astimezone(IST).isoformat()


def greeting() -> str:
    hour = now_ist().hour
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"


def classify_freshness(ts: datetime | None, delayed_feed: bool = True) -> str:
    if ts is None:
        return "UNAVAILABLE"
    age = (datetime.now(ts.tzinfo or IST) - ts).total_seconds()
    if age < 0:
        age = 0
    if delayed_feed:
        if age <= 24 * 3600:
            return "DELAYED"
        return "HISTORICAL"
    if age <= 60:
        return "REAL-TIME"
    if age <= 15 * 60:
        return "NEAR REAL-TIME"
    if age <= 24 * 3600:
        return "DELAYED"
    return "HISTORICAL"
