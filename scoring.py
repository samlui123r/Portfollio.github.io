"""
scoring.py - Compute per-video and per-cluster metrics.

Per-video:
  - views_per_day
  - evergreen_flag
  - recent_momentum_flag
  - dominance_flag

Per-cluster:
  - total_views, average_views, median_views
  - average_video_age_days, average_views_per_day
  - cluster_status: growing | saturated | underserved | evergreen | unclear
  - opportunity_score (1–10)
  - representative_titles (top 3 by views)
"""

import math
import statistics
import logging
from typing import Optional

import pandas as pd

from config import (
    EVERGREEN_MIN_AGE_DAYS,
    EVERGREEN_MIN_VIEWS_PER_DAY,
    RECENT_MOMENTUM_MAX_AGE_DAYS,
    RECENT_MOMENTUM_MIN_VPD,
    DOMINANCE_MIN_QUERIES,
    ALL_CLUSTERS,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# PER-VIDEO METRICS
# ─────────────────────────────────────────────

def compute_video_metrics(rows: list[dict]) -> list[dict]:
    """
    Add per-video scoring fields to each row. Returns the same list.
    """
    for row in rows:
        views     = row.get("view_count") or 0
        age_days  = row.get("video_age_days") or 1
        mqc       = row.get("matched_queries_count") or 1

        vpd = round(views / max(age_days, 1), 2)
        row["views_per_day"] = vpd

        row["evergreen_flag"] = bool(
            age_days >= EVERGREEN_MIN_AGE_DAYS
            and vpd >= EVERGREEN_MIN_VIEWS_PER_DAY
        )
        row["recent_momentum_flag"] = bool(
            age_days <= RECENT_MOMENTUM_MAX_AGE_DAYS
            and vpd >= RECENT_MOMENTUM_MIN_VPD
        )
        row["dominance_flag"] = bool(mqc >= DOMINANCE_MIN_QUERIES)

    return rows


# ─────────────────────────────────────────────
# NICHE TYPE CLASSIFICATION
# ─────────────────────────────────────────────

def classify_niche_type(channel_description: str, channel_name: str) -> str:
    """
    Classify a channel into niche_type.
    Returns one of: niche-specific | broad business/finance | broad generalist | unclear
    """
    from config import NICHE_SPECIFIC_KEYWORDS, BROAD_BUSINESS_KEYWORDS

    text = (channel_description + " " + channel_name).lower()

    niche_hits = sum(1 for kw in NICHE_SPECIFIC_KEYWORDS if kw in text)
    broad_hits  = sum(1 for kw in BROAD_BUSINESS_KEYWORDS if kw in text)

    if niche_hits >= 2:
        return "niche-specific"
    elif niche_hits == 1 or broad_hits >= 3:
        return "broad business/finance"
    elif broad_hits >= 1:
        return "broad generalist"
    else:
        return "unclear"


# ─────────────────────────────────────────────
# PER-CLUSTER AGGREGATIONS
# ─────────────────────────────────────────────

def compute_cluster_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Given the full video DataFrame, return a cluster-level summary DataFrame.
    """
    records = []

    for cluster in ALL_CLUSTERS:
        cdf = df[df["primary_cluster"] == cluster]
        n = len(cdf)

        if n == 0:
            records.append({
                "cluster":               cluster,
                "number_of_videos":      0,
                "total_views":           0,
                "average_views":         0,
                "median_views":          0,
                "average_video_age_days":None,
                "average_views_per_day": 0,
                "cluster_status":        "unclear",
                "opportunity_score":     1,
                "representative_titles": "",
            })
            continue

        views_series = cdf["view_count"].dropna()
        vpd_series   = cdf["views_per_day"].dropna()
        age_series   = cdf["video_age_days"].dropna()

        total_views   = int(views_series.sum()) if len(views_series) else 0
        avg_views     = round(views_series.mean(), 1) if len(views_series) else 0
        median_views  = round(views_series.median(), 1) if len(views_series) else 0
        avg_age       = round(age_series.mean(), 1) if len(age_series) else None
        avg_vpd       = round(vpd_series.mean(), 2) if len(vpd_series) else 0

        status = _cluster_status(n, avg_views, avg_age, avg_vpd)
        opp    = _opportunity_score(n, avg_vpd, avg_age, status)

        # Representative titles: top 3 by views
        top_rows = cdf.nlargest(3, "view_count")[["video_title"]].values.flatten()
        rep_titles = " | ".join(str(t) for t in top_rows if t)

        records.append({
            "cluster":               cluster,
            "number_of_videos":      n,
            "total_views":           total_views,
            "average_views":         avg_views,
            "median_views":          median_views,
            "average_video_age_days":avg_age,
            "average_views_per_day": avg_vpd,
            "cluster_status":        status,
            "opportunity_score":     opp,
            "representative_titles": rep_titles,
        })

    return pd.DataFrame(records).sort_values("opportunity_score", ascending=False)


# ─────────────────────────────────────────────
# HEURISTIC STATUS & SCORE
# ─────────────────────────────────────────────

def _cluster_status(
    n: int,
    avg_views: float,
    avg_age: Optional[float],
    avg_vpd: float,
) -> str:
    """
    Determine cluster status using transparent heuristics.

    Logic:
      growing      → high VPD, relatively young content, decent volume
      saturated    → high video count + high views but aging content
      underserved  → very few videos despite search demand signals
      evergreen    → older content still pulling steady daily views
      unclear      → not enough data
    """
    if n < 3:
        return "underserved" if n > 0 else "unclear"

    avg_age_safe = avg_age or 365

    if avg_vpd >= 200 and avg_age_safe <= 180:
        return "growing"
    if n >= 15 and avg_views >= 50_000 and avg_age_safe >= 365:
        return "saturated"
    if n <= 5:
        return "underserved"
    if avg_vpd >= 80 and avg_age_safe >= 180:
        return "evergreen"
    if avg_vpd >= 150:
        return "growing"
    return "unclear"


def _opportunity_score(
    n: int,
    avg_vpd: float,
    avg_age: Optional[float],
    status: str,
) -> int:
    """
    Produce an opportunity score 1–10 using weighted heuristics.

    Higher score = better opportunity for a new creator to target this cluster.

    Factors:
      - Demand proxy:      avg_vpd (higher = more viewer interest)
      - Competition proxy: n (fewer videos = less competition)
      - Recency:           younger avg_age = more active market
      - Status bonus:      underserved +2, growing +1, saturated -2
    """
    score = 5.0  # baseline

    # Demand signal (0-3 pts)
    if avg_vpd >= 500:
        score += 3
    elif avg_vpd >= 200:
        score += 2
    elif avg_vpd >= 80:
        score += 1
    elif avg_vpd < 20:
        score -= 1

    # Competition proxy (0-2 pts)
    if n <= 5:
        score += 2
    elif n <= 10:
        score += 1
    elif n >= 30:
        score -= 1

    # Recency
    avg_age_safe = avg_age or 365
    if avg_age_safe <= 90:
        score += 1
    elif avg_age_safe >= 730:
        score -= 1

    # Status adjustments
    if status == "underserved":
        score += 2
    elif status == "growing":
        score += 1
    elif status == "saturated":
        score -= 2

    return int(min(10, max(1, round(score))))


# ─────────────────────────────────────────────
# CHANNEL DOMINANT ANGLE
# ─────────────────────────────────────────────

def dominant_angle(video_rows: list[dict]) -> str:
    """
    Given a list of video rows for a single channel,
    return the most common primary_cluster as the channel's dominant angle.
    """
    if not video_rows:
        return "unclear"
    from collections import Counter
    counts = Counter(r.get("primary_cluster", "other") for r in video_rows)
    return counts.most_common(1)[0][0]
