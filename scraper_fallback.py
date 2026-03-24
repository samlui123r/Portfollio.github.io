"""
scraper_fallback.py - Playwright-based fallback for when no YOUTUBE_API_KEY is set.

NOTE: This module is ONLY used when YOUTUBE_API_KEY is missing.
      Install playwright with:  pip install playwright && playwright install chromium

The fallback returns the same stub shape as youtube_api.search_videos so that
the rest of the pipeline is completely unaware of which data source was used.

Limitations vs the API:
  - No reliable subscriber counts (YouTube hides them from unauthenticated users)
  - View / like counts scraped from the search result page (less stable)
  - Pagination is limited by how many scroll events we can perform
  - Results may vary by region / IP
"""

import re
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

_PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    logger.warning(
        "playwright not installed. Fallback scraping unavailable. "
        "Install with: pip install playwright && playwright install chromium"
    )


# ─────────────────────────────────────────────
# PUBLIC INTERFACE
# ─────────────────────────────────────────────

def search_videos_fallback(query: str, max_results: int = 30) -> list[dict]:
    """
    Scrape YouTube search results for `query` using Playwright.
    Returns a list of video stubs (same shape as youtube_api.search_videos).
    Falls back to an empty list with a warning if Playwright is unavailable.
    """
    if not _PLAYWRIGHT_AVAILABLE:
        logger.error(
            "Playwright is not installed. Cannot use scraper fallback. "
            "Either install playwright or set YOUTUBE_API_KEY."
        )
        return _demo_stubs(query, n=5)

    stubs = []
    search_url = f"https://www.youtube.com/results?search_query={_url_encode(query)}&sp=EgIQAQ%3D%3D"
    # sp= filter: Videos only

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            )
            page = ctx.new_page()
            page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)

            # Accept cookies if prompted (EU / region banners)
            try:
                page.click("button[aria-label='Accept all']", timeout=3000)
            except Exception:
                pass

            # Scroll to load more results
            for _ in range(max(1, max_results // 10)):
                page.keyboard.press("End")
                time.sleep(0.8)

            # Parse ytInitialData JSON embedded in the page
            html = page.content()
            browser.close()

        stubs = _parse_search_html(html, query, max_results)
    except Exception as exc:
        logger.error(f"Playwright scraping failed: {exc}")
        stubs = _demo_stubs(query, n=5)

    return stubs[:max_results]


def get_video_details_fallback(video_ids: list[str]) -> dict[str, dict]:
    """
    Minimal fallback: returns empty stats dicts so pipeline doesn't break.
    Full per-video scraping is omitted to avoid rate-limiting risk.
    """
    return {vid: {"view_count": None, "like_count": None, "comment_count": None}
            for vid in video_ids}


def get_channel_details_fallback(channel_ids: list[str]) -> dict[str, dict]:
    """Returns empty channel detail dicts as placeholders."""
    return {cid: {"subscriber_count": None, "total_video_count": None,
                  "channel_description": ""}
            for cid in channel_ids}


# ─────────────────────────────────────────────
# PARSING HELPERS
# ─────────────────────────────────────────────

def _parse_search_html(html: str, query: str, max_results: int) -> list[dict]:
    """
    Extract video stubs from YouTube's ytInitialData JSON blob in the page HTML.
    This is fragile by nature – YouTube changes its structure occasionally.
    """
    import json

    stubs = []
    # Extract the JSON blob
    match = re.search(r"var ytInitialData\s*=\s*(\{.*?\});\s*</script>", html, re.DOTALL)
    if not match:
        logger.warning("Could not find ytInitialData in page HTML.")
        return stubs

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        logger.warning(f"JSON parse error on ytInitialData: {exc}")
        return stubs

    # Walk into the contents tree
    try:
        sections = (
            data["contents"]["twoColumnSearchResultsRenderer"]
            ["primaryContents"]["sectionListRenderer"]["contents"]
        )
    except (KeyError, TypeError):
        logger.warning("Unexpected ytInitialData structure.")
        return stubs

    rank = 1
    for section in sections:
        items = (
            section.get("itemSectionRenderer", {}).get("contents", [])
        )
        for item in items:
            vr = item.get("videoRenderer")
            if not vr:
                continue
            vid_id = vr.get("videoId", "")
            title_runs = vr.get("title", {}).get("runs", [])
            title = "".join(r.get("text", "") for r in title_runs)
            channel_runs = (
                vr.get("ownerText", {}).get("runs", [])
                or vr.get("longBylineText", {}).get("runs", [])
            )
            channel_name = "".join(r.get("text", "") for r in channel_runs)
            channel_id = ""
            nav_ep = (channel_runs[0].get("navigationEndpoint", {}) if channel_runs else {})
            channel_id = (
                nav_ep.get("browseEndpoint", {}).get("browseId", "")
            )
            pub_text = ""
            for meta in vr.get("publishedTimeText", {}).get("runs", [{}]):
                pub_text = meta.get("text", "")
            thumb = (
                vr.get("thumbnail", {}).get("thumbnails", [{}])[-1].get("url", "")
            )
            desc_runs = vr.get("detailedMetadataSnippets", [{}])
            desc = ""
            if desc_runs:
                desc_snip = desc_runs[0].get("snippetText", {}).get("runs", [])
                desc = "".join(r.get("text", "") for r in desc_snip)

            stubs.append({
                "video_id":            vid_id,
                "video_title":         title,
                "channel_id":          channel_id,
                "channel_name":        channel_name,
                "published_at":        pub_text,   # relative e.g. "2 months ago"
                "description_snippet": desc,
                "thumbnail_url":       thumb,
                "query_rank":          rank,
            })
            rank += 1
            if rank > max_results:
                return stubs
    return stubs


def _url_encode(text: str) -> str:
    from urllib.parse import quote_plus
    return quote_plus(text)


# ─────────────────────────────────────────────
# DEMO STUBS (last-resort when nothing works)
# ─────────────────────────────────────────────

def _demo_stubs(query: str, n: int = 5) -> list[dict]:
    """
    Return clearly-labeled placeholder stubs so the pipeline can still
    produce skeleton output files for inspection.
    """
    logger.warning(f"Returning {n} DEMO stubs for query: '{query}'")
    stubs = []
    for i in range(1, n + 1):
        stubs.append({
            "video_id":            f"DEMO_{query[:10].replace(' ', '_')}_{i}",
            "video_title":         f"[DEMO] {query} – example video {i}",
            "channel_id":          f"DEMO_CHANNEL_{i}",
            "channel_name":        f"Demo Channel {i}",
            "published_at":        "2024-01-01T00:00:00Z",
            "description_snippet": "Demo result – no API key or scraper available.",
            "thumbnail_url":       "",
            "query_rank":          i,
        })
    return stubs
