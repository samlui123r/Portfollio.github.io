"""
main.py - YouTube Niche Research Pipeline
Niche: Business Credit / No-Doc Funding for New LLCs

Run:
    python main.py

Requires YOUTUBE_API_KEY environment variable (or falls back to scraper/demo stubs).
"""

import json
import logging
import sys
from collections import defaultdict

import pandas as pd
from tqdm import tqdm

# ── Project imports ──────────────────────────
from config import (
    SEARCH_QUERIES,
    MAX_RESULTS_PER_QUERY,
    RAW_RESULTS_CSV,
    CHANNELS_CSV,
    CLUSTER_CSV,
    OUTPUT_DIR,
)
import youtube_api
import scraper_fallback
from normalize import normalize_video_row, normalize_channel_row
from cluster import assign_clusters_batch, detect_hook_patterns
from scoring import compute_video_metrics, compute_cluster_summary, classify_niche_type, dominant_angle
from report_builder import build_report, build_summary_json

# ── Logging ──────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(OUTPUT_DIR / "run.log", mode="w"),
    ],
)
logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════
# STEP 1 – COLLECT VIDEO STUBS
# ═════════════════════════════════════════════

def collect_stubs() -> dict[str, list[dict]]:
    """
    Run all search queries and return dict of query → list[video_stub].
    Uses YouTube API if key is available, otherwise falls back to scraper/demo.
    """
    use_api = youtube_api.api_available()
    if use_api:
        logger.info("YouTube API key detected — using Data API v3.")
        search_fn = youtube_api.search_videos
    else:
        logger.warning("No YOUTUBE_API_KEY found — using scraper/demo fallback.")
        search_fn = scraper_fallback.search_videos_fallback

    results: dict[str, list[dict]] = {}
    for query in tqdm(SEARCH_QUERIES, desc="Searching queries"):
        try:
            stubs = search_fn(query, MAX_RESULTS_PER_QUERY)
            results[query] = stubs
            logger.info(f"  '{query}' → {len(stubs)} stubs")
        except Exception as exc:
            logger.error(f"  Failed query '{query}': {exc}")
            results[query] = []
    return results


# ═════════════════════════════════════════════
# STEP 2 – DEDUPLICATE ACROSS QUERIES
# ═════════════════════════════════════════════

def deduplicate(query_stubs: dict[str, list[dict]]) -> list[dict]:
    """
    Merge stubs from all queries, deduplicating by video_id.
    Adds: first_seen_query, all_matched_queries, matched_queries_count.
    """
    seen: dict[str, dict] = {}         # video_id → merged stub
    video_queries: dict[str, list] = defaultdict(list)

    for query, stubs in query_stubs.items():
        for stub in stubs:
            vid_id = stub.get("video_id", "")
            if not vid_id:
                continue
            video_queries[vid_id].append(query)
            if vid_id not in seen:
                seen[vid_id] = dict(stub)
                seen[vid_id]["search_query"]      = query
                seen[vid_id]["first_seen_query"]  = query

    deduped = []
    for vid_id, stub in seen.items():
        queries = video_queries[vid_id]
        stub["all_matched_queries"]    = "; ".join(queries)
        stub["matched_queries_count"]  = len(queries)
        deduped.append(stub)

    logger.info(f"Deduplicated to {len(deduped)} unique videos from "
                f"{sum(len(v) for v in query_stubs.values())} total stubs.")
    return deduped


# ═════════════════════════════════════════════
# STEP 3 – ENRICH WITH VIDEO + CHANNEL DETAILS
# ═════════════════════════════════════════════

def enrich_videos(stubs: list[dict]) -> list[dict]:
    """
    Fetch detailed statistics for all unique video IDs (batch calls).
    Merges stats back into stubs in-place.
    """
    video_ids = [s["video_id"] for s in stubs if s.get("video_id")]

    if youtube_api.api_available():
        logger.info(f"Fetching video details for {len(video_ids)} videos …")
        details = youtube_api.get_video_details(video_ids)
    else:
        details = scraper_fallback.get_video_details_fallback(video_ids)

    for stub in stubs:
        vid_id = stub.get("video_id", "")
        d = details.get(vid_id, {})
        stub.update({
            "view_count":    d.get("view_count"),
            "like_count":    d.get("like_count"),
            "comment_count": d.get("comment_count"),
        })
        # Prefer detailed published_at over search snippet if available
        if d.get("published_at"):
            stub["published_at"] = d["published_at"]
        if d.get("description_snippet"):
            stub["description_snippet"] = d["description_snippet"]

    return stubs


def enrich_channels(stubs: list[dict]) -> dict[str, dict]:
    """
    Fetch channel details for all unique channel IDs.
    Returns dict: channel_id → channel detail dict.
    """
    channel_ids = list({s["channel_id"] for s in stubs if s.get("channel_id")})
    logger.info(f"Fetching channel details for {len(channel_ids)} channels …")

    if youtube_api.api_available():
        channel_details = youtube_api.get_channel_details(channel_ids)
    else:
        channel_details = scraper_fallback.get_channel_details_fallback(channel_ids)

    return channel_details


# ═════════════════════════════════════════════
# STEP 4 – BUILD DATAFRAMES
# ═════════════════════════════════════════════

def build_videos_df(stubs: list[dict]) -> pd.DataFrame:
    """Normalise, cluster, and score all video rows."""
    # Normalise
    rows = [normalize_video_row(s) for s in stubs]

    # Cluster
    rows = assign_clusters_batch(rows)

    # Score
    rows = compute_video_metrics(rows)

    df = pd.DataFrame(rows)
    return df


def build_channels_df(
    stubs: list[dict],
    channel_details: dict[str, dict],
) -> pd.DataFrame:
    """Build the channels DataFrame."""
    # Aggregate relevant video counts per channel
    channel_video_map: dict[str, list] = defaultdict(list)
    for stub in stubs:
        cid = stub.get("channel_id", "")
        if cid:
            channel_video_map[cid].append(stub)

    records = []
    for cid, vid_rows in channel_video_map.items():
        sample = vid_rows[0]
        detail = channel_details.get(cid, {})

        ch_desc = detail.get("channel_description", "")
        ch_name = sample.get("channel_name", "")

        niche = classify_niche_type(ch_desc, ch_name)
        dom   = dominant_angle(vid_rows)

        rec = {
            "channel_id":              cid,
            "channel_name":            ch_name,
            "channel_url":             f"https://www.youtube.com/channel/{cid}",
            "subscriber_count":        detail.get("subscriber_count"),
            "total_video_count":       detail.get("total_video_count"),
            "channel_description_snippet": ch_desc[:200] if ch_desc else "",
            "relevant_videos_found":   len(vid_rows),
            "niche_type":              niche,
            "dominant_angle":          dom,
            "notes":                   "",
        }
        rec = normalize_channel_row(rec)
        records.append(rec)

    df = pd.DataFrame(records).sort_values("relevant_videos_found", ascending=False)
    return df


# ═════════════════════════════════════════════
# STEP 5 – EXPORT CSVs
# ═════════════════════════════════════════════

def export_raw_results(df: pd.DataFrame):
    """Write raw_results.csv with the required column set."""
    cols_map = {
        "search_query":           "Search Query",
        "video_title":            "Video Title",
        "video_url":              "Video URL",
        "channel_name":           "Channel Name",
        "channel_url":            "Channel URL",
        "subscriber_count":       "Subscribers",
        "view_count":             "Views",
        "upload_date_normalized": "Upload Date",
        "video_age_days":         "Video Age Days",
        "query_rank":             "Query Rank",
        "matched_queries_count":  "Matched Queries Count",
        "primary_cluster":        "Theme Cluster",
        "secondary_cluster":      "Secondary Cluster",
        "views_per_day":          "Views Per Day",
        "evergreen_flag":         "Evergreen Flag",
        "recent_momentum_flag":   "Recent Momentum Flag",
        "dominance_flag":         "Dominance Flag",
        "thumbnail_url":          "Thumbnail URL",
    }
    out = df[[c for c in cols_map if c in df.columns]].rename(columns=cols_map)
    out.to_csv(RAW_RESULTS_CSV, index=False, encoding="utf-8")
    logger.info(f"raw_results.csv → {len(out)} rows")


def export_channels(df: pd.DataFrame):
    """Write channels.csv."""
    cols_map = {
        "channel_name":           "Channel Name",
        "channel_url":            "Channel URL",
        "subscriber_count":       "Subscribers",
        "total_video_count":      "Total Videos",
        "relevant_videos_found":  "Relevant Videos Found",
        "niche_type":             "Niche Type",
        "dominant_angle":         "Dominant Angle",
        "notes":                  "Notes",
    }
    out = df[[c for c in cols_map if c in df.columns]].rename(columns=cols_map)
    out.to_csv(CHANNELS_CSV, index=False, encoding="utf-8")
    logger.info(f"channels.csv → {len(out)} rows")


def export_cluster_summary(df: pd.DataFrame):
    """Write cluster_summary.csv."""
    df.to_csv(CLUSTER_CSV, index=False, encoding="utf-8")
    logger.info(f"cluster_summary.csv → {len(df)} rows")


# ═════════════════════════════════════════════
# MAIN PIPELINE
# ═════════════════════════════════════════════

def main():
    logger.info("=" * 60)
    logger.info("YouTube Niche Research — Business Credit / LLC Funding")
    logger.info("=" * 60)

    # 1. Collect
    query_stubs = collect_stubs()

    # 2. Deduplicate
    stubs = deduplicate(query_stubs)

    if not stubs:
        logger.error("No video stubs collected. Exiting.")
        sys.exit(1)

    # 3. Enrich
    stubs = enrich_videos(stubs)
    channel_details = enrich_channels(stubs)

    # 4. Build DataFrames
    logger.info("Building video DataFrame …")
    videos_df = build_videos_df(stubs)

    logger.info("Building channel DataFrame …")
    channels_df = build_channels_df(stubs, channel_details)

    # Merge subscriber_count into videos_df from channels_df
    sub_map = channels_df.set_index("channel_id")["subscriber_count"].to_dict()
    if "channel_id" in videos_df.columns:
        videos_df["subscriber_count"] = videos_df["channel_id"].map(sub_map)

    # 5. Cluster summary + scoring
    logger.info("Computing cluster summary …")
    cluster_df = compute_cluster_summary(videos_df)

    # 6. Hook patterns
    logger.info("Detecting hook patterns …")
    titles = videos_df["video_title"].dropna().tolist()
    hook_patterns = detect_hook_patterns(titles)

    # 7. Export CSVs
    logger.info("Exporting CSVs …")
    export_raw_results(videos_df)
    export_channels(channels_df)
    export_cluster_summary(cluster_df)

    # 8. Reports
    logger.info("Building report …")
    build_report(videos_df, channels_df, cluster_df, hook_patterns)
    build_summary_json(videos_df, channels_df, cluster_df, hook_patterns)

    logger.info("=" * 60)
    logger.info("Pipeline complete. Output files:")
    logger.info(f"  {RAW_RESULTS_CSV}")
    logger.info(f"  {CHANNELS_CSV}")
    logger.info(f"  {CLUSTER_CSV}")
    from config import REPORT_MD, SUMMARY_JSON
    logger.info(f"  {REPORT_MD}")
    logger.info(f"  {SUMMARY_JSON}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
