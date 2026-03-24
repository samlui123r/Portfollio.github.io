"""
youtube_api.py - YouTube Data API v3 client.

Handles:
  - Search queries  → list of video stubs
  - Video details   → views, likes, comments, duration
  - Channel details → subscribers, total video count, description
"""

import time
import logging
from typing import Optional

import requests

from config import (
    YOUTUBE_API_KEY,
    YOUTUBE_API_BASE,
    MAX_RESULTS_PER_QUERY,
    RESULTS_PAGE_SIZE,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _get(endpoint: str, params: dict, retries: int = 3) -> Optional[dict]:
    """GET request against the YouTube API with simple retry logic."""
    params["key"] = YOUTUBE_API_KEY
    url = f"{YOUTUBE_API_BASE}/{endpoint}"
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 403:
                logger.error("YouTube API 403 – quota exceeded or bad key.")
                return None
            elif resp.status_code == 429:
                wait = 2 ** attempt
                logger.warning(f"Rate limited. Waiting {wait}s …")
                time.sleep(wait)
            else:
                logger.warning(f"HTTP {resp.status_code} for {url}")
                return None
        except requests.RequestException as exc:
            logger.warning(f"Request error (attempt {attempt+1}): {exc}")
            time.sleep(2)
    return None


# ─────────────────────────────────────────────
# SEARCH
# ─────────────────────────────────────────────

def search_videos(query: str, max_results: int = MAX_RESULTS_PER_QUERY) -> list[dict]:
    """
    Search YouTube for `query` and return up to `max_results` video stubs.

    Each stub contains:
        video_id, video_title, channel_id, channel_name,
        published_at, thumbnail_url, description_snippet, query_rank
    """
    stubs = []
    page_token = None
    rank = 1

    while len(stubs) < max_results:
        fetch = min(RESULTS_PAGE_SIZE, max_results - len(stubs))
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": fetch,
            "relevanceLanguage": "en",
            "order": "relevance",
        }
        if page_token:
            params["pageToken"] = page_token

        data = _get("search", params)
        if not data:
            break

        for item in data.get("items", []):
            vid_id = item.get("id", {}).get("videoId")
            if not vid_id:
                continue
            snippet = item.get("snippet", {})
            thumb = (
                snippet.get("thumbnails", {})
                .get("high", {})
                .get("url", "")
                or snippet.get("thumbnails", {})
                .get("default", {})
                .get("url", "")
            )
            stubs.append({
                "video_id":           vid_id,
                "video_title":        snippet.get("title", ""),
                "channel_id":         snippet.get("channelId", ""),
                "channel_name":       snippet.get("channelTitle", ""),
                "published_at":       snippet.get("publishedAt", ""),
                "description_snippet": snippet.get("description", ""),
                "thumbnail_url":      thumb,
                "query_rank":         rank,
            })
            rank += 1

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return stubs[:max_results]


# ─────────────────────────────────────────────
# VIDEO DETAILS (batch up to 50 IDs per call)
# ─────────────────────────────────────────────

def get_video_details(video_ids: list[str]) -> dict[str, dict]:
    """
    Fetch statistics + contentDetails for a list of video IDs.
    Returns a dict keyed by video_id.
    """
    details = {}
    # API allows max 50 ids per request
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i : i + 50]
        params = {
            "part": "statistics,contentDetails,snippet",
            "id": ",".join(chunk),
        }
        data = _get("videos", params)
        if not data:
            continue
        for item in data.get("items", []):
            vid_id = item["id"]
            stats = item.get("statistics", {})
            snippet = item.get("snippet", {})
            details[vid_id] = {
                "view_count":    _safe_int(stats.get("viewCount")),
                "like_count":    _safe_int(stats.get("likeCount")),
                "comment_count": _safe_int(stats.get("commentCount")),
                "published_at":  snippet.get("publishedAt", ""),
                "description_snippet": snippet.get("description", "")[:300],
            }
    return details


# ─────────────────────────────────────────────
# CHANNEL DETAILS (batch up to 50 IDs per call)
# ─────────────────────────────────────────────

def get_channel_details(channel_ids: list[str]) -> dict[str, dict]:
    """
    Fetch statistics + snippet for a list of channel IDs.
    Returns a dict keyed by channel_id.
    """
    details = {}
    for i in range(0, len(channel_ids), 50):
        chunk = channel_ids[i : i + 50]
        params = {
            "part": "statistics,snippet",
            "id": ",".join(chunk),
        }
        data = _get("channels", params)
        if not data:
            continue
        for item in data.get("items", []):
            cid = item["id"]
            stats = item.get("statistics", {})
            snippet = item.get("snippet", {})
            details[cid] = {
                "subscriber_count":   _safe_int(stats.get("subscriberCount")),
                "total_video_count":  _safe_int(stats.get("videoCount")),
                "channel_description": snippet.get("description", "")[:300],
            }
    return details


# ─────────────────────────────────────────────
# UTILS
# ─────────────────────────────────────────────

def _safe_int(val) -> Optional[int]:
    """Safely cast a value to int, returning None if not possible."""
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def api_available() -> bool:
    """Return True if YOUTUBE_API_KEY is set and non-empty."""
    return bool(YOUTUBE_API_KEY)
