"""
cluster.py - Keyword-based topic clustering for YouTube videos.

Each video gets:
  - primary_cluster
  - secondary_cluster  (next best match, or empty)
  - cluster_confidence  (0.0 – 1.0 based on match density)
"""

import re
import logging
from typing import Optional

from config import CLUSTERS, CLUSTER_OTHER

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# PRE-COMPILE KEYWORD PATTERNS
# ─────────────────────────────────────────────

_CLUSTER_PATTERNS: dict[str, list[re.Pattern]] = {}
for _cluster, _keywords in CLUSTERS.items():
    _CLUSTER_PATTERNS[_cluster] = [
        re.compile(r"\b" + re.escape(kw.lower()) + r"\b") for kw in _keywords
    ]


# ─────────────────────────────────────────────
# CORE SCORING
# ─────────────────────────────────────────────

def _score_text(text: str) -> dict[str, int]:
    """Return a dict of cluster → keyword hit count for a given text."""
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for cluster, patterns in _CLUSTER_PATTERNS.items():
        hits = sum(1 for p in patterns if p.search(text_lower))
        if hits:
            scores[cluster] = hits
    return scores


def assign_clusters(
    title: str,
    description: str = "",
    weight_title: float = 2.0,
    weight_desc: float = 1.0,
) -> dict:
    """
    Assign primary_cluster, secondary_cluster, and cluster_confidence
    to a video based on its title and description snippet.

    Returns:
        {
          "primary_cluster":    str,
          "secondary_cluster":  str,
          "cluster_confidence": float (0.0-1.0)
        }
    """
    title_scores = _score_text(title)
    desc_scores  = _score_text(description)

    # Combine with weights
    combined: dict[str, float] = {}
    all_keys = set(title_scores) | set(desc_scores)
    for k in all_keys:
        combined[k] = (
            title_scores.get(k, 0) * weight_title
            + desc_scores.get(k, 0) * weight_desc
        )

    if not combined:
        return {
            "primary_cluster":    CLUSTER_OTHER,
            "secondary_cluster":  "",
            "cluster_confidence": 0.0,
        }

    sorted_clusters = sorted(combined.items(), key=lambda x: x[1], reverse=True)

    primary   = sorted_clusters[0][0]
    primary_s = sorted_clusters[0][1]
    secondary = sorted_clusters[1][0] if len(sorted_clusters) > 1 else ""
    secondary_s = sorted_clusters[1][1] if len(sorted_clusters) > 1 else 0

    # Confidence: ratio of top score to total score (normalised 0-1)
    total = sum(v for _, v in sorted_clusters)
    confidence = round(primary_s / total, 3) if total else 0.0

    # Boost confidence if title alone matches primary
    if primary in title_scores:
        confidence = min(1.0, confidence * 1.2)

    return {
        "primary_cluster":    primary,
        "secondary_cluster":  secondary,
        "cluster_confidence": round(confidence, 3),
    }


# ─────────────────────────────────────────────
# BATCH ASSIGN
# ─────────────────────────────────────────────

def assign_clusters_batch(rows: list[dict]) -> list[dict]:
    """
    Add cluster fields to each row dict in-place. Returns the same list.
    Expects each row to have at least 'video_title' key.
    """
    for row in rows:
        title = row.get("video_title", "")
        desc  = row.get("description_snippet", "")
        result = assign_clusters(title, desc)
        row.update(result)
    return rows


# ─────────────────────────────────────────────
# HOOK / PATTERN DETECTION
# ─────────────────────────────────────────────

def detect_hook_patterns(titles: list[str]) -> dict[str, int]:
    """
    Count occurrences of each hook pattern across a list of titles.
    Returns dict of pattern_name → count.
    """
    from config import HOOK_PATTERNS

    counts: dict[str, int] = {name: 0 for name in HOOK_PATTERNS}
    for title in titles:
        title_lower = title.lower()
        for name, pattern in HOOK_PATTERNS.items():
            if re.search(pattern, title_lower, re.IGNORECASE):
                counts[name] += 1

    # Remove zero counts
    return {k: v for k, v in counts.items() if v > 0}
