"""
normalize.py - Normalise raw video and channel data.

Handles:
  - Date parsing (ISO-8601, relative strings from scraper)
  - YYYY-MM-DD upload_date_normalized
  - video_age_days from today
  - Integer coercion for counts
  - Building canonical video_url and channel_url
"""

import re
import logging
from datetime import date, datetime, timezone
from typing import Optional

from dateutil import parser as dateutil_parser
from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)

TODAY = date.today()


# ─────────────────────────────────────────────
# DATE NORMALISATION
# ─────────────────────────────────────────────

def parse_published_at(raw: str) -> Optional[date]:
    """
    Parse a published_at string into a Python date.

    Accepts:
      - ISO-8601: "2024-03-15T12:00:00Z"
      - Relative: "2 months ago", "3 years ago", "1 week ago"
      - Plain date: "2024-03-15"
    Returns None if parsing fails.
    """
    if not raw:
        return None
    raw = raw.strip()

    # Try ISO / standard first
    try:
        return dateutil_parser.parse(raw).date()
    except Exception:
        pass

    # Relative strings from scraper fallback
    relative = _parse_relative_date(raw)
    if relative:
        return relative

    logger.debug(f"Could not parse date: {raw!r}")
    return None


def _parse_relative_date(text: str) -> Optional[date]:
    """Convert YouTube relative strings like '3 months ago' to a date."""
    text = text.lower().strip()
    patterns = [
        (r"(\d+)\s+year",   "years"),
        (r"(\d+)\s+month",  "months"),
        (r"(\d+)\s+week",   "weeks"),
        (r"(\d+)\s+day",    "days"),
        (r"(\d+)\s+hour",   "hours"),
        (r"(\d+)\s+minute", "minutes"),
    ]
    for pattern, unit in patterns:
        m = re.search(pattern, text)
        if m:
            n = int(m.group(1))
            delta_kwargs = {unit: n}
            try:
                dt = datetime.now(timezone.utc) - relativedelta(**delta_kwargs)
                return dt.date()
            except Exception:
                pass
    return None


def upload_date_normalized(raw: str) -> str:
    """Return YYYY-MM-DD string or empty string."""
    d = parse_published_at(raw)
    return d.strftime("%Y-%m-%d") if d else ""


def video_age_days(raw: str) -> Optional[int]:
    """Return integer days since upload, or None."""
    d = parse_published_at(raw)
    if d:
        return (TODAY - d).days
    return None


# ─────────────────────────────────────────────
# INTEGER COERCION
# ─────────────────────────────────────────────

def safe_int(val) -> Optional[int]:
    """Safely convert val to int; return None on failure."""
    if val is None:
        return None
    try:
        return int(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


# ─────────────────────────────────────────────
# URL BUILDERS
# ─────────────────────────────────────────────

def video_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}" if video_id else ""


def channel_url(channel_id: str) -> str:
    return f"https://www.youtube.com/channel/{channel_id}" if channel_id else ""


# ─────────────────────────────────────────────
# FULL ROW NORMALISER
# ─────────────────────────────────────────────

def normalize_video_row(row: dict) -> dict:
    """
    Accept a raw merged dict and return a normalised copy.
    Adds:  upload_date_normalized, video_age_days, video_url, channel_url
    Coerces: view_count, like_count, comment_count, subscriber_count
    """
    r = dict(row)

    pub_raw = r.get("published_at", "")
    r["upload_date_normalized"] = upload_date_normalized(pub_raw)
    r["video_age_days"]         = video_age_days(pub_raw)
    r["video_url"]              = video_url(r.get("video_id", ""))
    r["channel_url"]            = channel_url(r.get("channel_id", ""))
    r["view_count"]             = safe_int(r.get("view_count"))
    r["like_count"]             = safe_int(r.get("like_count"))
    r["comment_count"]          = safe_int(r.get("comment_count"))
    r["subscriber_count"]       = safe_int(r.get("subscriber_count"))

    return r


def normalize_channel_row(row: dict) -> dict:
    """Normalise a channel row."""
    r = dict(row)
    r["subscriber_count"]  = safe_int(r.get("subscriber_count"))
    r["total_video_count"] = safe_int(r.get("total_video_count"))
    r["channel_url"]       = channel_url(r.get("channel_id", ""))
    return r
