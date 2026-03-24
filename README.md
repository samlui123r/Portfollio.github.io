# YouTube Niche Research — Business Credit / No-Doc Funding for New LLCs

A fully automated Python research pipeline that collects, normalises, clusters,
scores, and reports on YouTube content in the **Business Credit / LLC Funding** niche.

---

## Project Structure

```
yt_research/
├── main.py               ← Entry point / pipeline orchestrator
├── youtube_api.py        ← YouTube Data API v3 client
├── scraper_fallback.py   ← Playwright-based fallback (no API key)
├── normalize.py          ← Date / count normalisation helpers
├── cluster.py            ← Keyword-based topic clustering
├── scoring.py            ← Video & cluster metric computation
├── report_builder.py     ← Markdown report + summary JSON generator
├── config.py             ← All constants, queries, cluster definitions
├── requirements.txt      ← Python dependencies
├── README.md             ← This file
└── output/               ← Created automatically on first run
    ├── raw_results.csv
    ├── channels.csv
    ├── cluster_summary.csv
    ├── report.md
    ├── summary.json
    └── run.log
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

If you intend to use the Playwright scraper fallback, also install the browser:

```bash
playwright install chromium
```

### 2. Set your YouTube API key

**macOS / Linux:**
```bash
export YOUTUBE_API_KEY="YOUR_KEY_HERE"
```

**Windows (PowerShell):**
```powershell
$env:YOUTUBE_API_KEY = "YOUR_KEY_HERE"
```

**Windows (Command Prompt):**
```cmd
set YOUTUBE_API_KEY=YOUR_KEY_HERE
```

> **How to get an API key:**
> 1. Go to https://console.cloud.google.com/
> 2. Create a new project (or select existing)
> 3. Enable the **YouTube Data API v3**
> 4. Create an API key under Credentials

### 3. Run the pipeline

```bash
python main.py
```

The pipeline typically takes **2–5 minutes** depending on API quota and network speed.

---

## Output Files

| File | Description |
|------|-------------|
| `output/raw_results.csv` | One row per unique video with all collected & computed fields |
| `output/channels.csv` | One row per unique channel with subscriber/video counts |
| `output/cluster_summary.csv` | Aggregated stats per topic cluster with opportunity scores |
| `output/report.md` | Full human-readable strategic research report |
| `output/summary.json` | Compact JSON summary for downstream tooling |
| `output/run.log` | Execution log with warnings and errors |

---

## API Quota Notes

The YouTube Data API v3 has a default quota of **10,000 units per day**.

Approximate cost for a full run:
- Search requests: 15 queries × ~2 pages × 100 units = **~3,000 units**
- Video detail requests: ~750 videos / 50 per call × 1 unit = **~15 units**
- Channel detail requests: ~200 channels / 50 per call × 1 unit = **~4 units**
- **Estimated total: ~3,020 units** (well within the daily limit)

If you hit quota limits, you'll see `403` errors in `run.log`. Wait until midnight
Pacific Time for the quota to reset.

---

## Fallback Mode (No API Key)

If `YOUTUBE_API_KEY` is not set:

1. The pipeline first tries to scrape YouTube search results using **Playwright**.
2. If Playwright is not installed, it falls back to **demo stub data** so you can
   inspect the output file structure without real data.

> Scraper fallback limitations:
> - No subscriber counts (hidden by YouTube for unauthenticated requests)
> - No precise view/like/comment counts from search pages
> - Rate limiting risk — avoid running too many queries too quickly
> - YouTube's page structure changes occasionally, breaking the parser

**Recommendation:** Always use the API key for production runs.

---

## Configuration

All settings are in `config.py`:

- `SEARCH_QUERIES` — add/remove queries here
- `MAX_RESULTS_PER_QUERY` — default 50 (YouTube API maximum per search)
- `CLUSTERS` — keyword rules for each topic cluster
- `HOOK_PATTERNS` — regex patterns for title analysis
- Scoring thresholds: `EVERGREEN_MIN_AGE_DAYS`, `RECENT_MOMENTUM_MIN_VPD`, etc.

---

## Example: Adding Custom Queries

Edit `config.py`:

```python
SEARCH_QUERIES = [
    # ... existing queries ...
    "SBA loan for new LLC",
    "DSCR loan business",
]
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `403 quota exceeded` | Wait for quota reset or use a second API key |
| `No module named playwright` | Run `pip install playwright && playwright install chromium` |
| Empty output files | Check `run.log` for errors; verify API key is set correctly |
| Date parsing warnings | Normal for relative dates from scraper; treated as approximate |
| `KeyError` in cluster_summary | Update pandas: `pip install --upgrade pandas` |
