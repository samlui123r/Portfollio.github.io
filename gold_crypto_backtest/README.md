# Gold & Crypto Backtest Engine
### 5-Strategy Quantitative Backtest System
**Assets:** BTCUSDT · ETHUSDT · SOLUSDT · XAUUSDT  
**Exchange:** Binance (Futures + Spot)  
**Engine:** vectorbt

---

## Project Structure

```
gold_crypto_backtest/
├── main.py                      ← Run everything from here
├── config.py                    ← All parameters live here
├── requirements.txt
├── data/
│   ├── fetcher.py               ← Binance data + NFP/expiry dates
│   └── cache/                   ← Auto-created, stores downloaded data
├── strategies/
│   ├── liquidity_sweep.py       ← Strategy 1
│   ├── volatility_coil.py       ← Strategy 2
│   ├── funding_exhaustion.py    ← Strategy 3
│   ├── nfp_compression.py       ← Strategy 4
│   └── gamma_squeeze.py         ← Strategy 5
├── indicators/
│   └── custom.py                ← All indicator logic (no TA-Lib needed)
├── analysis/
│   └── reporter.py              ← Stats, plots, CSV exports
└── results/                     ← Auto-created, all outputs saved here
```

---

## VPS Setup (Ubuntu 22.04 — Recommended)

### 1. Provision VPS
Recommended: Hetzner CX21 (€4.15/mo) or AWS t3.medium ($0.04/hr)
- 2 vCPU, 4GB RAM, 40GB SSD — sufficient for full backtest

### 2. Connect & install Python
```bash
ssh root@YOUR_VPS_IP

# Update system
apt update && apt upgrade -y

# Install Python 3.11+
apt install python3.11 python3.11-pip python3.11-venv git -y

# Verify
python3.11 --version
```

### 3. Clone / upload project
```bash
# Option A: Upload via SCP from your machine
scp -r ./gold_crypto_backtest root@YOUR_VPS_IP:/root/

# Option B: Git clone if you push to a repo
git clone https://github.com/YOUR_REPO/gold_crypto_backtest.git
cd gold_crypto_backtest
```

### 4. Create virtual environment
```bash
cd /root/gold_crypto_backtest
python3.11 -m venv venv
source venv/bin/activate
```

### 5. Install dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> **Note:** vectorbt installation can take 3–5 minutes. If it fails, try:
> `pip install vectorbt --no-deps` then install dependencies separately.

---

## Running the Backtest

### Run all 5 strategies (default)
```bash
python main.py
```

### Run a single strategy
```bash
python main.py --strategy liquidity    # Liquidity Sweep
python main.py --strategy coil         # Volatility Coil
python main.py --strategy funding      # Funding Exhaustion
python main.py --strategy nfp          # Pre-NFP Compression
python main.py --strategy gamma        # Gamma Squeeze
```

### Run with parameter optimization
```bash
python main.py --optimize              # All strategies + grid search
python main.py --strategy coil --optimize  # Single strategy optimized
```

### Skip plots (for headless VPS)
```bash
python main.py --no-plots              # Saves PNG files but doesn't display
```

### Full production run
```bash
python main.py --optimize --no-plots 2>&1 | tee backtest_run.log
```

---

## What Gets Saved to /results/

| File | Description |
|------|-------------|
| `backtest_summary.csv` | All strategies — key metrics table |
| `equity_*.png` | Equity curves per strategy |
| `heatmap_*.png` | Monthly returns heatmaps |
| `opt_*.csv` | Optimization grid search results |
| `*_trades.csv` | Individual trade logs (entry/exit/PnL) |

---

## Configuration

All parameters are in `config.py`. Key settings:

```python
INITIAL_CAPITAL  = 10_000    # Starting equity in USD
LEVERAGE         = 25        # Applied for return estimation
TAKER_FEE        = 0.0004   # Binance futures taker (0.04%)
RISK_PER_TRADE   = 0.03     # 3% of equity per trade
BACKTEST_START   = "2022-01-01"
BACKTEST_END     = "2024-12-31"
```

To change strategy parameters, edit the corresponding section:
```python
LIQUIDITY_SWEEP = {
    "swing_lookback": 20,
    "sweep_threshold": 0.0015,
    ...
}
```

---

## Understanding the Output

### Console Summary Table Columns
- `Total Return %` — Unlevered backtest return
- `Lev Return %`   — Estimated leveraged return (Total × Leverage)
- `Max Drawdown %` — Largest peak-to-trough loss (unleveraged)
- `Lev Max DD %`   — Estimated leveraged drawdown
- `Win Rate %`     — % of trades that hit TP before SL
- `Sharpe`         — Risk-adjusted return (aim for > 1.5)
- `Trades/Month`   — Signal frequency

### Interpreting Leveraged Returns
Leveraged estimates are LINEAR approximations only.
True leveraged returns depend on:
- Position sizing model
- Margin maintenance
- Liquidation price relative to SL
- Slippage at leverage

Always validate with a paper trading period before going live.

---

## Data Caching

First run downloads all OHLCV + funding data from Binance.
This takes approximately:
- 15M BTC: ~3 minutes (3 years of data)
- 4H BTC:  ~30 seconds
- Funding rates: ~2 minutes per symbol

Subsequent runs use cached `.parquet` files from `data/cache/`.
To force re-download: `python main.py --no-cache`

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'vectorbt'`**
```bash
source venv/bin/activate  # Make sure venv is activated
pip install vectorbt
```

**Binance rate limit errors**
```
ccxt.base.errors.RateLimitExceeded
```
Normal — fetcher has automatic retry logic. Wait and re-run.

**XAUUSDT not found on Binance futures**
Gold trades on Binance Spot only. The fetcher handles this automatically.
If issues persist, check Binance symbol: it may be `XAUUSDT` or `XAUTUSDT`.

**vectorbt Portfolio.stats() missing keys**
Some metrics require minimum trade count. If `n_trades < 5`, stats will be partial.
This is expected for NFP Compression (only 1 trade/month).

---

## Next Steps After Backtesting

1. **Identify top 2–3 configs** from optimization CSVs (sort by Sharpe > 1.5)
2. **Walk-forward validate** — test on 2024 data only (out-of-sample)
3. **Paper trade** — run signals on Binance testnet for 2–4 weeks
4. **Build live bot** — connect signal generation to Binance API order execution

The live trading bot module will be built separately after backtest validation.

---

## Disclaimer

This is a research and backtesting tool only.
Past backtest performance does not guarantee future results.
High leverage trading carries significant risk of total capital loss.
Never risk capital you cannot afford to lose.
