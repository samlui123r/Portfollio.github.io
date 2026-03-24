"""
config.py - Central configuration for the YouTube niche research project.
All constants, query lists, cluster definitions, and settings live here.
"""

import os
from pathlib import Path

# ─────────────────────────────────────────────
# API CONFIGURATION
# ─────────────────────────────────────────────
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
MAX_RESULTS_PER_QUERY = 50   # YouTube API max per request is 50
RESULTS_PAGE_SIZE = 50       # items per page for list calls

# ─────────────────────────────────────────────
# OUTPUT PATHS
# ─────────────────────────────────────────────
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

RAW_RESULTS_CSV   = OUTPUT_DIR / "raw_results.csv"
CHANNELS_CSV      = OUTPUT_DIR / "channels.csv"
CLUSTER_CSV       = OUTPUT_DIR / "cluster_summary.csv"
REPORT_MD         = OUTPUT_DIR / "report.md"
SUMMARY_JSON      = OUTPUT_DIR / "summary.json"

# ─────────────────────────────────────────────
# SEARCH QUERIES
# ─────────────────────────────────────────────
SEARCH_QUERIES = [
    "business credit for new LLC",
    "no doc business funding",
    "funding for new LLC",
    "EIN only business funding",
    "startup business credit",
    "no revenue business funding",
    "new LLC business loans",
    "business credit cards for new LLC",
    "0 APR business credit for startups",
    "how to get funding for a new business",
    "net 30 accounts for new LLC",
    "business tradelines for startups",
    "credit stacking business funding",
    "no collateral business funding",
    "business funding without tax returns",
]

# ─────────────────────────────────────────────
# TOPIC CLUSTERS & KEYWORD RULES
# ─────────────────────────────────────────────
CLUSTERS = {
    "beginner education": [
        "what is business credit", "beginner", "explain", "introduction",
        "101", "basics", "start here", "what you need to know",
        "getting started", "overview", "guide for beginners",
    ],
    "step-by-step funding tutorials": [
        "step by step", "step-by-step", "how to get", "how i got",
        "tutorial", "walkthrough", "complete guide", "full process",
        "exact steps", "follow along",
    ],
    "credit stacking": [
        "credit stack", "credit stacking", "stacking credit",
        "multiple cards", "stack funding", "layering credit",
    ],
    "EIN-only / no-PG strategies": [
        "ein only", "ein-only", "no personal guarantee", "no pg",
        "no ssn", "without ssn", "without social security",
        "business only credit", "separate from personal",
    ],
    "no-doc funding claims": [
        "no doc", "no-doc", "no documentation", "no docs",
        "without documents", "without tax returns", "no statements",
        "no bank statements", "no financials",
    ],
    "startup loan approvals": [
        "approved", "approval", "get approved", "loan approval",
        "i got approved", "just got approved", "loan for new business",
        "startup loan", "business loan",
    ],
    "vendor tradelines / net-30": [
        "net 30", "net-30", "vendor", "tradeline", "trade line",
        "vendor account", "vendor credit", "net30", "uline",
        "quill", "grainger", "office depot",
    ],
    "LLC setup for funding": [
        "llc setup", "set up llc", "form llc", "new llc",
        "just formed", "brand new llc", "structure your llc",
        "llc for funding", "llc for credit",
    ],
    "myths / mistakes / traps": [
        "mistake", "mistakes", "avoid", "trap", "scam", "warning",
        "don't do", "do not", "myth", "lies", "truth about",
        "real truth", "exposed", "red flags",
    ],
    "bank relationships and underwriting": [
        "bank relationship", "underwriting", "bank account",
        "banking", "lender", "underwriter", "bank tier",
        "bank ready", "bank references",
    ],
    "business credit cards": [
        "credit card", "credit cards", "business card",
        "business cards", "visa", "mastercard", "amex",
        "american express", "chase ink", "capital one spark",
        "0 apr", "0% apr", "zero apr", "intro apr",
    ],
    "funding amounts / proof screenshots / case studies": [
        "$100k", "$100,000", "100k", "$50k", "50k", "$250k",
        "proof", "screenshot", "case study", "case studies",
        "i got funded", "results", "success story",
    ],
    "no revenue funding": [
        "no revenue", "zero revenue", "without revenue",
        "no income", "no sales", "day 1", "day one",
        "brand new business", "no history",
    ],
    "no collateral funding": [
        "no collateral", "unsecured", "without collateral",
        "no assets", "without assets",
    ],
}
CLUSTER_OTHER = "other"
ALL_CLUSTERS = list(CLUSTERS.keys()) + [CLUSTER_OTHER]

# ─────────────────────────────────────────────
# NICHE TYPE CLASSIFICATION KEYWORDS
# ─────────────────────────────────────────────
NICHE_SPECIFIC_KEYWORDS = [
    "business credit", "llc funding", "ein only", "no doc funding",
    "net 30", "tradeline", "credit stacking", "startup funding",
    "business loan", "no revenue", "no collateral",
]
BROAD_BUSINESS_KEYWORDS = [
    "entrepreneur", "business", "finance", "investing", "money",
    "wealth", "income", "passive income", "side hustle",
]

# ─────────────────────────────────────────────
# TITLE HOOK PATTERNS (regex)
# ─────────────────────────────────────────────
HOOK_PATTERNS = {
    "How to get ...":        r"\bhow to get\b",
    "New LLC ...":           r"\bnew llc\b",
    "No doc ...":            r"\bno[- ]doc\b",
    "Get approved ...":      r"\bget approved\b",
    "EIN only ...":          r"\bein[- ]only\b",
    "Dollar amount claim":   r"\$\d[\d,k]+",
    "Top N ...":             r"\btop \d+\b",
    "Step by step ...":      r"\bstep[- ]by[- ]step\b",
    "Without revenue ...":   r"\bwithout revenue\b",
    "Fastest way ...":       r"\bfastest way\b",
    "Don't do this ...":     r"\bdon'?t do\b",
    "Urgency words":         r"\b(urgent|fast|quick|instantly|today|now|2024|2025)\b",
    "Approval language":     r"\b(approved|approval|qualify|qualified)\b",
    "Proof/screenshot":      r"\b(proof|screenshot|results|case study|case studies)\b",
    "No PG/SSN/collateral":  r"\b(no pg|no ssn|no collateral|no personal guarantee)\b",
}

# ─────────────────────────────────────────────
# SCORING THRESHOLDS
# ─────────────────────────────────────────────
EVERGREEN_MIN_AGE_DAYS       = 180   # older than 6 months
EVERGREEN_MIN_VIEWS_PER_DAY  = 50    # still pulling decent daily views
RECENT_MOMENTUM_MAX_AGE_DAYS = 90    # published within 3 months
RECENT_MOMENTUM_MIN_VPD      = 100   # high early velocity
DOMINANCE_MIN_QUERIES        = 3     # appears in 3+ queries

OPPORTUNITY_WEIGHTS = {
    "avg_vpd":        0.35,
    "underserved":    0.30,
    "search_volume":  0.20,
    "avg_age_recency":0.15,
}
