"""
=============================================================
 BACKTEST CONFIGURATION
 All strategy parameters live here — edit before running
=============================================================
"""

# ─── GLOBAL SETTINGS ─────────────────────────────────────
INITIAL_CAPITAL     = 10_000        # USD
LEVERAGE            = 25            # Applied to all strategies (adjust per strat)
TAKER_FEE           = 0.0004        # Binance USDT-M futures taker fee (0.04%)
MAKER_FEE           = 0.0002        # Binance USDT-M futures maker fee (0.02%)
SLIPPAGE            = 0.0005        # 0.05% per side
RISK_PER_TRADE      = 0.03          # 3% of equity risked per trade
BACKTEST_START      = "2022-01-01"
BACKTEST_END        = "2024-12-31"

# ─── ASSETS ──────────────────────────────────────────────
ASSETS = {
    "liquidity_sweep"     : ["BTCUSDT", "ETHUSDT", "XAUUSDT"],
    "volatility_coil"     : ["BTCUSDT", "SOLUSDT", "ETHUSDT"],
    "funding_exhaustion"  : ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    "nfp_compression"     : ["XAUUSDT"],        # Gold only
    "gamma_squeeze"       : ["BTCUSDT"],
}

TIMEFRAMES = {
    "liquidity_sweep"     : "15m",
    "volatility_coil"     : "4h",
    "funding_exhaustion"  : "4h",
    "nfp_compression"     : "1h",
    "gamma_squeeze"       : "4h",
}

# ─── STRATEGY 1: LIQUIDITY SWEEP REVERSAL ─────────────────
LIQUIDITY_SWEEP = {
    "swing_lookback"        : 20,       # candles to detect swing low/high
    "sweep_threshold"       : 0.0015,   # 0.15% below swing low to confirm sweep
    "wick_rejection_pct"    : 0.70,     # close must be in top 70% of candle range
    "rsi_period"            : 14,
    "rsi_threshold"         : 35,       # RSI must be below this at sweep
    "tp1_swing_lookback"    : 20,       # bars to find TP1 target (prior swing high)
    "sl_buffer"             : 0.0003,   # 0.03% below sweep wick
    "tp2_multiplier"        : 2.0,      # 2x sweep distance for TP2
    # Parameter sweep ranges (for optimization)
    "opt_swing_lookback"    : [10, 15, 20, 25, 30],
    "opt_sweep_threshold"   : [0.001, 0.0015, 0.002, 0.0025, 0.003],
    "opt_rsi_threshold"     : [25, 30, 35, 40, 45],
    "opt_wick_rejection"    : [0.60, 0.65, 0.70, 0.75, 0.80],
}

# ─── STRATEGY 2: VOLATILITY COIL BREAKOUT ─────────────────
VOLATILITY_COIL = {
    "atr_short"             : 7,
    "atr_long"              : 50,
    "atr_ratio_threshold"   : 0.40,     # ATR(7)/ATR(50) < 0.40 = compressed
    "bb_period"             : 20,
    "bb_std"                : 2.0,
    "volume_sma_period"     : 20,
    "volume_multiplier"     : 1.5,      # volume must be 1.5x avg
    "tp_atr_multiplier"     : 2.5,      # TP = 2.5x ATR(14) from entry
    "sl_lookback"           : 10,       # SL = lowest low of last 10 candles
    "time_stop_candles"     : 8,        # exit if no move in 8 candles
    "atr_tp_period"         : 14,
    # Optimization ranges
    "opt_atr_ratio"         : [0.30, 0.35, 0.40, 0.45, 0.50, 0.55],
    "opt_bb_period"         : [15, 18, 20, 23, 25, 30],
    "opt_volume_mult"       : [1.2, 1.3, 1.5, 1.8, 2.0],
    "opt_tp_multiplier"     : [2.0, 2.5, 3.0, 3.5, 4.0],
}

# ─── STRATEGY 3: FUNDING RATE EXHAUSTION ─────────────────
FUNDING_EXHAUSTION = {
    "funding_threshold"     : 0.0008,   # 0.08% per 8H = extreme
    "funding_ma_period"     : 3,        # 3-day MA (in 8H periods = 9 periods)
    "funding_trend_periods" : 5,        # MA must be rising for 5 consecutive periods
    "oi_lookback"           : 3,        # days to detect OI divergence
    "price_lookback"        : 3,        # days for price comparison
    "momentum_crack_period" : 1,        # 4H candles for crack confirmation
    "tp_atr_multiplier"     : 3.0,
    "sl_swing_lookback"     : 10,       # SL above most recent swing high
    "time_stop_hours"       : 48,
    # Optimization ranges
    "opt_funding_threshold" : [0.0005, 0.0006, 0.0008, 0.001, 0.0012],
    "opt_trend_periods"     : [3, 4, 5, 6, 7, 8],
    "opt_oi_lookback"       : [2, 3, 5, 7],
}

# ─── STRATEGY 4: PRE-NFP COMPRESSION ─────────────────────
NFP_COMPRESSION = {
    "pre_nfp_hours"         : 48,       # hours before NFP to measure range
    "compression_pct"       : 0.60,     # range must be < 60% of ATR(14)
    "atr_period"            : 14,
    "tp_range_multiplier"   : 2.5,      # TP = 2.5x compression range
    "fill_window_minutes"   : 15,       # cancel if not filled within 15min
    "nfp_release_hour_utc"  : 13,
    "nfp_release_min_utc"   : 30,
    "hard_exit_hour_utc"    : 17,       # 17:00 UTC hard close
    "spread_abort_pips"     : 50,       # abort if spread > 50 pips
    # Optimization ranges
    "opt_pre_nfp_hours"     : [24, 36, 48, 60, 72],
    "opt_compression_pct"   : [0.50, 0.55, 0.60, 0.65, 0.70, 0.75],
    "opt_tp_multiplier"     : [2.0, 2.5, 3.0, 3.5],
}

# ─── STRATEGY 5: GAMMA SQUEEZE (PROXY-BASED) ─────────────
GAMMA_SQUEEZE = {
    "pre_expiry_hours"      : 72,       # hours before monthly expiry
    "max_pain_proxy_period" : 30,       # days for VWAP as max-pain proxy
    "distance_threshold"    : 0.04,     # price must be > 4% from proxy level
    "momentum_candles"      : 2,        # candles moving toward max-pain
    "sl_distance_pct"       : 0.025,    # 2.5% away from max-pain = stop
    "oi_proxy_period"       : 14,       # rolling period for OI proxy
    # Optimization ranges
    "opt_distance_threshold": [0.03, 0.04, 0.05, 0.06, 0.07],
    "opt_pre_expiry_hours"  : [48, 60, 72, 84, 96],
    "opt_momentum_candles"  : [1, 2, 3],
}

# ─── OUTPUT SETTINGS ─────────────────────────────────────
RESULTS_DIR         = "results"
SAVE_PLOTS          = True
SAVE_CSV            = True
PRINT_TRADE_LOG     = False     # Set True to see every trade
