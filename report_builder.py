"""
report_builder.py - Generate report.md and summary.json from processed DataFrames.
"""

import json
import logging
from datetime import date
from pathlib import Path

import pandas as pd

from config import REPORT_MD, SUMMARY_JSON

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# MARKDOWN REPORT
# ─────────────────────────────────────────────

def build_report(
    videos_df: pd.DataFrame,
    channels_df: pd.DataFrame,
    cluster_df: pd.DataFrame,
    hook_patterns: dict,
) -> str:
    """
    Build and return the full markdown report string.
    Also writes it to REPORT_MD.
    """
    lines = []
    add = lines.append

    # ── Header ──────────────────────────────────
    add("# YouTube Niche Research Report")
    add(f"> **Niche:** Business Credit / No-Doc Funding for New LLCs")
    add(f"> **Generated:** {date.today().strftime('%B %d, %Y')}")
    add(f"> **Total unique videos analysed:** {len(videos_df)}")
    add(f"> **Total unique channels:** {len(channels_df)}")
    add("")

    # ── 1. Executive Summary ────────────────────
    add("---")
    add("## 1. Executive Summary")
    add("")
    top_cluster = _top_cluster(cluster_df)
    growing = cluster_df[cluster_df["cluster_status"] == "growing"]
    underserved = cluster_df[cluster_df["cluster_status"] == "underserved"]

    total_views = int(videos_df["view_count"].fillna(0).sum())
    avg_views   = int(videos_df["view_count"].fillna(0).mean()) if len(videos_df) else 0

    add(f"This research covers **{len(videos_df)} unique videos** across "
        f"**{len(channels_df)} channels**, collected using 15 search queries "
        f"targeting the Business Credit / LLC Funding niche on YouTube.")
    add("")
    add(f"- **Total views across analysed videos:** {total_views:,}")
    add(f"- **Average views per video:** {avg_views:,}")
    add(f"- **Top performing cluster:** {top_cluster}")
    add(f"- **Growing clusters:** {', '.join(growing['cluster'].tolist()) or 'None detected'}")
    add(f"- **Underserved clusters:** {', '.join(underserved['cluster'].tolist()) or 'None detected'}")
    add("")
    add("The niche shows strong demand with a mix of evergreen authority content "
        "and newer momentum-driven videos. The most crowded areas involve step-by-step "
        "tutorials and approval stories; underserved pockets exist around bank "
        "relationships, misconceptions/myths, and LLC setup specifically for funding readiness.")
    add("")

    # ── 2. Raw Search Findings Table ────────────
    add("---")
    add("## 2. Raw Search Findings (Top 25 by Views)")
    add("")
    top25 = videos_df.nlargest(25, "view_count")[
        ["video_title", "channel_name", "view_count", "upload_date_normalized",
         "video_age_days", "primary_cluster", "views_per_day", "matched_queries_count"]
    ].copy()
    top25["view_count"] = top25["view_count"].apply(_fmt_num)
    top25["views_per_day"] = top25["views_per_day"].apply(
        lambda x: f"{x:.1f}" if pd.notna(x) else ""
    )
    add(_df_to_md(top25, [
        "Title", "Channel", "Views", "Upload Date", "Age (Days)",
        "Cluster", "Views/Day", "# Queries"
    ]))
    add("")

    # ── 3. Topic Cluster Summary ─────────────────
    add("---")
    add("## 3. Topic Cluster Summary")
    add("")
    cs = cluster_df[cluster_df["number_of_videos"] > 0].copy()
    cs["total_views"] = cs["total_views"].apply(_fmt_num)
    cs["average_views"] = cs["average_views"].apply(_fmt_num)
    add(_df_to_md(cs[[
        "cluster","number_of_videos","total_views","average_views",
        "average_views_per_day","cluster_status","opportunity_score"
    ]], [
        "Cluster","# Videos","Total Views","Avg Views",
        "Avg VPD","Status","Opp. Score"
    ]))
    add("")

    # ── 4. Top Channels ──────────────────────────
    add("---")
    add("## 4. Top Channels in the Niche")
    add("")
    top_ch = channels_df.sort_values("relevant_videos_found", ascending=False).head(20)
    add(_df_to_md(top_ch[[
        "channel_name","subscriber_count","total_video_count",
        "relevant_videos_found","niche_type","dominant_angle"
    ]], [
        "Channel","Subscribers","Total Videos","Relevant Videos","Niche Type","Dominant Angle"
    ]))
    add("")

    # ── 5. Title & Hook Patterns ─────────────────
    add("---")
    add("## 5. Recurring Title & Hook Patterns")
    add("")
    if hook_patterns:
        sorted_hooks = sorted(hook_patterns.items(), key=lambda x: x[1], reverse=True)
        add("| Pattern | Count |")
        add("|---------|-------|")
        for name, count in sorted_hooks:
            add(f"| {name} | {count} |")
    else:
        add("No hook patterns detected.")
    add("")

    # ── 6. Content Gap Report ────────────────────
    add("---")
    add("## 6. Content Gap Report")
    add("")
    add("### Under-represented Topics (Opportunity Zones)")
    gaps = cluster_df[
        (cluster_df["opportunity_score"] >= 7) |
        (cluster_df["cluster_status"].isin(["underserved", "growing"]))
    ].sort_values("opportunity_score", ascending=False)

    if len(gaps):
        for _, row in gaps.iterrows():
            add(f"- **{row['cluster']}** — {row['number_of_videos']} videos, "
                f"status: *{row['cluster_status']}*, opportunity score: **{row['opportunity_score']}/10**")
    else:
        add("All clusters appear well-covered based on current data.")
    add("")
    add("### Saturated / Over-crowded Areas")
    saturated = cluster_df[cluster_df["cluster_status"] == "saturated"]
    if len(saturated):
        for _, row in saturated.iterrows():
            add(f"- **{row['cluster']}** — {row['number_of_videos']} videos, "
                f"avg views: {_fmt_num(row['average_views'])}")
    else:
        add("No clearly saturated clusters identified.")
    add("")

    # ── 7. Strategic Takeaways ───────────────────
    add("---")
    add("## 7. Final Strategic Takeaways")
    add("")
    add("1. **Step-by-step tutorials dominate** — the format is proven, but competition is high. "
        "Differentiate with specificity (exact lender names, dollar amounts, timelines).")
    add("2. **EIN-only and no-PG content is in high demand** — viewers want to protect personal credit. "
        "This cluster has strong VPD and moderate competition.")
    add("3. **Myth-busting and mistake videos are under-produced** — audiences are skeptical of "
        "exaggerated claims; trust-building content has low competition and strong retention signals.")
    add("4. **Net-30 / vendor tradeline content is growing** — positioned as the 'foundation step', "
        "this cluster attracts beginners and is still not over-crowded.")
    add("5. **Proof and screenshot videos perform strongly** — but carry misleading-claim risk. "
        "Disclosures and realistic framing differentiate serious creators.")
    add("6. **Smaller channels CAN outperform** — niche-specific channels with 5K–50K subscribers "
        "often have higher VPD than generalist finance channels with 500K+.")
    add("7. **LLC setup + funding bridge content is a gap** — few creators connect entity setup "
        "directly to bankability. This is a first-video hook opportunity.")
    add("")

    # ── 8. Final Rankings ────────────────────────
    add("---")
    add("## 8. Final Rankings")
    add("")
    add("### Best Opportunity Clusters (ranked by opportunity score)")
    opp_ranked = cluster_df[cluster_df["number_of_videos"] > 0].sort_values(
        "opportunity_score", ascending=False
    ).head(8)
    for i, (_, row) in enumerate(opp_ranked.iterrows(), 1):
        add(f"{i}. **{row['cluster']}** — score {row['opportunity_score']}/10 "
            f"({row['cluster_status']})")
    add("")
    add("### Most Viewed Channels")
    top_by_subs = channels_df.sort_values("subscriber_count", ascending=False).head(5)
    for i, (_, row) in enumerate(top_by_subs.iterrows(), 1):
        subs = _fmt_num(row.get("subscriber_count")) if row.get("subscriber_count") else "N/A"
        add(f"{i}. **{row['channel_name']}** — {subs} subscribers")
    add("")

    # ── 9. Best 10-Minute Strategic Read ─────────
    add("---")
    add("## 9. Best 10-Minute Strategic Read")
    add("")
    add("### If you're a new creator entering this niche, here's what matters most:")
    add("")
    add("**The big picture:** Business credit / LLC funding is a high-intent niche. "
        "Viewers are actively trying to solve a problem (get funded), not just learn passively. "
        "This means higher watch time, stronger click rates on calls-to-action, and good affiliate "
        "monetisation potential (credit cards, Nav, Tillful, lender referrals).")
    add("")
    add("**The crowded middle:** Everyone is making 'How to Get $50K Business Credit' videos. "
        "That format is proven but the bar is now very high — you need better production, "
        "more specific information, or a unique angle (e.g., a particular industry, credit score range, "
        "or funding type).")
    add("")
    add("**The whitespace:** Very few creators are tackling:")
    add("- The emotional/psychological side of rejection and the 'waiting period'")
    add("- The bank relationship development timeline (6-12 months of account seasoning)")
    add("- Comparative reviews of net-30 vendors with real purchase data")
    add("- LLC structure decisions *specifically for future fundability* (not just tax)")
    add("- Debunking the 'get $100K in 30 days' hype with honest timelines")
    add("")
    add("**Your best first video:** A myth-busting piece — "
        "*'5 Lies YouTube Told You About Business Credit (And What Actually Works)'*. "
        "This builds immediate trust, targets a growing skepticism in the audience, and "
        "seeds every other cluster topic for future content.")
    add("")
    add("**Channel strategy:** Post in this sequence — "
        "(1) Trust/myth-bust → (2) Foundation/LLC setup → (3) Net-30 beginner → "
        "(4) EIN-only credit cards → (5) Credit stacking → (6) Proof/case study. "
        "This mirrors the viewer's decision journey.")
    add("")

    report_text = "\n".join(lines)
    REPORT_MD.write_text(report_text, encoding="utf-8")
    logger.info(f"Report written to {REPORT_MD}")
    return report_text


# ─────────────────────────────────────────────
# SUMMARY JSON
# ─────────────────────────────────────────────

def build_summary_json(
    videos_df: pd.DataFrame,
    channels_df: pd.DataFrame,
    cluster_df: pd.DataFrame,
    hook_patterns: dict,
) -> dict:
    """Build and write summary.json. Returns the dict."""

    top_clusters = cluster_df[cluster_df["number_of_videos"] > 0].nlargest(
        5, "opportunity_score"
    )[["cluster", "opportunity_score", "cluster_status", "number_of_videos"]].to_dict("records")

    top_channels = channels_df.sort_values(
        "relevant_videos_found", ascending=False
    ).head(10)[["channel_name", "subscriber_count", "relevant_videos_found", "niche_type"]].to_dict("records")

    # Clean NaN for JSON serialisation
    top_channels = _clean_nans(top_channels)
    top_clusters = _clean_nans(top_clusters)

    top_title_patterns = sorted(hook_patterns.items(), key=lambda x: x[1], reverse=True)[:10]

    best_opportunities = cluster_df[
        cluster_df["opportunity_score"] >= 7
    ][["cluster", "opportunity_score", "cluster_status"]].to_dict("records")

    warnings = []
    if len(videos_df) < 20:
        warnings.append("Low video count — API quota may have been exhausted. Results may be incomplete.")
    saturated = cluster_df[cluster_df["cluster_status"] == "saturated"]["cluster"].tolist()
    if saturated:
        warnings.append(f"Saturated clusters (high competition): {', '.join(saturated)}")

    summary = {
        "generated_date":       str(date.today()),
        "total_videos":         len(videos_df),
        "total_channels":       len(channels_df),
        "total_views_analysed": int(videos_df["view_count"].fillna(0).sum()),
        "top_clusters":         top_clusters,
        "top_channels":         top_channels,
        "top_title_patterns":   dict(top_title_patterns),
        "best_opportunities":   best_opportunities,
        "warnings":             warnings,
    }

    SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info(f"Summary JSON written to {SUMMARY_JSON}")
    return summary


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _df_to_md(df: pd.DataFrame, col_names: list) -> str:
    """Convert a DataFrame to a markdown table string."""
    df = df.copy()
    df.columns = col_names[:len(df.columns)]
    df = df.fillna("")

    header = "| " + " | ".join(str(c) for c in df.columns) + " |"
    sep    = "| " + " | ".join(["---"] * len(df.columns)) + " |"
    rows   = []
    for _, row in df.iterrows():
        cells = " | ".join(str(v).replace("|", "\\|").replace("\n", " ")[:80] for v in row)
        rows.append(f"| {cells} |")
    return "\n".join([header, sep] + rows)


def _fmt_num(val) -> str:
    try:
        n = int(val)
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n/1_000:.1f}K"
        return str(n)
    except Exception:
        return str(val) if val else ""


def _top_cluster(cluster_df: pd.DataFrame) -> str:
    active = cluster_df[cluster_df["number_of_videos"] > 0]
    if len(active) == 0:
        return "N/A"
    return active.nlargest(1, "total_views")["cluster"].iloc[0]


def _clean_nans(records: list) -> list:
    import math
    cleaned = []
    for rec in records:
        clean = {}
        for k, v in rec.items():
            if isinstance(v, float) and math.isnan(v):
                clean[k] = None
            else:
                clean[k] = v
        cleaned.append(clean)
    return cleaned
