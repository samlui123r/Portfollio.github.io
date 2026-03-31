# 🚀 BINANCE VERSION - Quick Setup Guide

## What Changed?

Your strategy now uses **Binance API** instead of Yahoo Finance!

### Benefits:
✅ **5+ YEARS of 15-minute data** (was limited to 60 days)
✅ **600+ trading pairs** (BTC, ETH, SOL, BNB, etc.)
✅ **Higher quality data** (direct from exchange)
✅ **No data limitations** on any timeframe
✅ **Optional API keys** (works without them!)

---

## ⚡ Super Quick Start (30 seconds)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Backtest
```bash
python run_binance_backtest.py
```

**That's it!** Works without API keys using public data.

---

## 🔑 Optional: Add API Keys (Recommended)

### Why?
- Higher rate limits
- Faster data fetching
- More stable

### How? (2 minutes)

**Step 1:** Go to https://www.binance.com/en/my/settings/api-management

**Step 2:** Create API → System Generated

**Step 3:** **ONLY enable "Enable Reading"** (DON'T enable trading!)

**Step 4:** Copy your keys

**Step 5:** Edit `config_binance.py`:
```python
BINANCE_API_KEY = "paste_your_api_key_here"
BINANCE_API_SECRET = "paste_your_secret_here"
```

**Step 6:** Run again:
```bash
python run_binance_backtest.py
```

✓ Now using authenticated API with higher limits!

---

## 📝 File Changes

### New Files:
- **binance_data.py** - Fetches data from Binance
- **config_binance.py** - API configuration (add your keys here)
- **vectorbt_backtest_binance.py** - Binance version of backtest
- **run_binance_backtest.py** - New runner script
- **README_BINANCE.md** - Full documentation

### Unchanged:
- **optimized_strategy.py** - Same strategy logic
- **requirements.txt** - Added `python-binance`

---

## 🎯 Usage Examples

### Your Original Request (5 years, 15 minutes)
```bash
python run_binance_backtest.py --period 5y --interval 15m
```

### Test Ethereum
```bash
python run_binance_backtest.py --symbol ETHUSDT
```

### 1-hour candles, 2 years
```bash
python run_binance_backtest.py --interval 1h --period 2y
```

### With API keys (command line)
```bash
python run_binance_backtest.py \
  --api-key "your_key" \
  --api-secret "your_secret"
```

### Optimize parameters
```bash
python run_binance_backtest.py --optimize
```

---

## 🔒 Security: API Keys

### What Permissions to Enable?
- ✅ **"Enable Reading"** ONLY
- ❌ **NOT** "Enable Spot & Margin Trading"
- ❌ **NOT** "Enable Futures"
- ❌ **NOT** "Enable Withdrawals"

### Why is this safe?
- Read-only access
- Can't trade
- Can't withdraw
- Can only read market data

### Where to Store Keys?
**Option 1:** In `config_binance.py` (easiest)
```python
BINANCE_API_KEY = "your_key"
BINANCE_API_SECRET = "your_secret"
```

**Option 2:** Command line (most secure)
```bash
python run_binance_backtest.py --api-key "..." --api-secret "..."
```

**Option 3:** No keys (works fine!)
```bash
python run_binance_backtest.py  # Uses public API
```

---

## 📊 What You Get

Same as before, but with MORE data:

### Output Files:
1. **backtest_results.html** - Interactive chart
2. **trade_log.csv** - All trades
3. **portfolio_value.csv** - Portfolio over time
4. **statistics.csv** - Performance metrics

### Statistics:
- Total Return
- Sharpe Ratio
- Max Drawdown
- Win Rate
- Profit Factor
- 30+ more metrics

---

## 🆚 Before vs After

| Feature | Yahoo Finance | Binance API |
|---------|--------------|-------------|
| 15m data | 60 days | **5+ years** ✅ |
| 1h data | 2 years | **5+ years** ✅ |
| Symbols | BTC only | **600+ pairs** ✅ |
| Quality | Good | **Exchange-grade** ✅ |

---

## ⚠️ Important Notes

### Symbol Format
- ✅ Use: `BTCUSDT` (with USDT)
- ❌ Not: `BTC`, `BTCUSD`, `BTC-USD`

### Binance.US Users
Edit `config_binance.py`:
```python
USE_BINANCE_US = True
```

### No API Keys?
Still works! Just uses public API with lower rate limits.

---

## 🛠️ Troubleshooting

### "Invalid symbol: BTCUSD"
**Fix:** Use `BTCUSDT` (with USDT)

### "Rate limit exceeded"
**Fix:** Add API keys OR wait a minute

### "No data retrieved"
**Fix:** 
- Check internet
- Try: `python run_binance_backtest.py --period 1y`
- Verify symbol exists on Binance

### "Module binance not found"
**Fix:** `pip install python-binance`

---

## 🎓 Examples

### Example 1: Basic 5-Year Test
```bash
# Default uses 5 years of 15-minute BTC data
python run_binance_backtest.py
```

### Example 2: Test Multiple Timeframes
```bash
# 15-minute
python run_binance_backtest.py --interval 15m --period 5y

# 1-hour
python run_binance_backtest.py --interval 1h --period 5y

# Daily
python run_binance_backtest.py --interval 1d --period 5y
```

### Example 3: Test Different Coins
```bash
# Ethereum
python run_binance_backtest.py --symbol ETHUSDT

# Solana
python run_binance_backtest.py --symbol SOLUSDT

# Binance Coin
python run_binance_backtest.py --symbol BNBUSDT
```

### Example 4: With Your API Keys
```bash
python run_binance_backtest.py \
  --api-key "your_api_key_here" \
  --api-secret "your_secret_here" \
  --symbol BTCUSDT \
  --interval 15m \
  --period 5y
```

### Example 5: Find Best Parameters
```bash
python run_binance_backtest.py --optimize
```

---

## 📚 Documentation

- **README_BINANCE.md** - Complete guide (start here!)
- **COMPARISON.md** - Strategy improvements explained
- **config_binance.py** - Configuration file
- **binance_data.py** - Data fetching code

---

## ✅ Checklist

- [ ] Install: `pip install -r requirements.txt`
- [ ] Test public: `python run_binance_backtest.py`
- [ ] (Optional) Create Binance API keys
- [ ] (Optional) Add keys to `config_binance.py`
- [ ] Test with keys: `python run_binance_backtest.py`
- [ ] View results: Open `backtest_results.html`
- [ ] Try different symbols: `--symbol ETHUSDT`
- [ ] Optimize: `--optimize`

---

## 🎉 You're Done!

You now have:
- ✅ 5 years of high-quality data
- ✅ 600+ tradable symbols
- ✅ Professional backtesting
- ✅ No data limitations

```bash
# Your 5-year backtest is one command away:
python run_binance_backtest.py
```

Happy backtesting! 🚀📈

---

## 💡 Next Steps

1. Run basic test (no keys needed)
2. Review results in `backtest_results.html`
3. Add API keys for better performance
4. Test different symbols and timeframes
5. Optimize parameters
6. Forward test on recent data
7. Paper trade before going live

Remember: This is for educational purposes. Always paper trade first! ⚠️
