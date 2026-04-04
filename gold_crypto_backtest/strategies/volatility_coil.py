"""
=============================================================
 STRATEGY 2: VOLATILITY COIL BREAKOUT (ATR RATIO FILTER)
 Asset  : BTC, SOL, ETH
 TF     : 4H
 Type   : Volatility expansion after compression
 Signal : ATR ratio compression + BB breakout + volume spike
=============================================================
"""

import pandas as pd
import numpy as np
import vectorbt as vbt
import logging
from itertools import product

from indicators.custom import (
    atr,
    atr_ratio,
    bollinger_bands,
    volume_spike,
    swing_lows,
    swing_highs,
    no_weekend_filter,
)
from config import VOLATILITY_COIL, INITIAL_CAPITAL, TAKER_FEE, SLIPPAGE, RISK_PER_TRADE

logger = logging.getLogger(__name__)


def generate_signals(
    df: pd.DataFrame,
    atr_short: int         = VOLATILITY_COIL["atr_short"],
    atr_long: int          = VOLATILITY_COIL["atr_long"],
    atr_ratio_thresh: float= VOLATILITY_COIL["atr_ratio_threshold"],
    bb_period: int         = VOLATILITY_COIL["bb_period"],
    bb_std: float          = VOLATILITY_COIL["bb_std"],
    vol_period: int        = VOLATILITY_COIL["volume_sma_period"],
    vol_mult: float        = VOLATILITY_COIL["volume_multiplier"],
    tp_atr_mult: float     = VOLATILITY_COIL["tp_atr_multiplier"],
    sl_lookback: int       = VOLATILITY_COIL["sl_lookback"],
    atr_tp_period: int     = VOLATILITY_COIL["atr_tp_period"],
    time_stop: int         = VOLATILITY_COIL["time_stop_candles"],
) -> dict:
    """
    Entry (long):
      - ATR(short)/ATR(long) < atr_ratio_thresh (compression)
      - Close > BB upper (breakout candle)
      - Volume > vol_mult × 20-period avg (conviction)
      - No weekend

    Entry (short):
      - ATR ratio < threshold (compression)
      - Close < BB lower (breakout candle)
      - Volume spike confirmed

    SL: Lowest low of last sl_lookback candles
    TP: tp_atr_mult × ATR(atr_tp_period) from entry
    """
    h = df["high"]
    l = df["low"]
    c = df["close"]
    v = df["volume"]

    # ── Compression filter ────────────────────────────────
    atr_r  = atr_ratio(h, l, c, atr_short, atr_long)
    compressed = atr_r < atr_ratio_thresh

    # ── Bollinger Band breakout ───────────────────────────
    bb_upper, bb_mid, bb_lower = bollinger_bands(c, bb_period, bb_std)
    break_up   = c > bb_upper
    break_down = c < bb_lower

    # ── Volume spike ──────────────────────────────────────
    vol_confirmed = volume_spike(v, vol_period, vol_mult)

    # ── Weekend filter ────────────────────────────────────
    no_weekend = no_weekend_filter(df.index)

    # ── Combined signals ──────────────────────────────────
    # Compression must be present 1 bar ago (coil was active before breakout)
    was_compressed = compressed.shift(1).fillna(False)

    entries_long  = was_compressed & break_up   & vol_confirmed & no_weekend
    entries_short = was_compressed & break_down & vol_confirmed & no_weekend

    # ── Stop Loss ─────────────────────────────────────────
    # Long SL: lowest low of last sl_lookback candles
    # Short SL: highest high of last sl_lookback candles
    recent_low  = l.rolling(sl_lookback).min()
    recent_high = h.rolling(sl_lookback).max()

    sl_long  = (c - recent_low) / c
    sl_short = (recent_high - c) / c
    sl_long  = sl_long.clip(lower=0.005, upper=0.08)
    sl_short = sl_short.clip(lower=0.005, upper=0.08)

    # ── Take Profit: ATR-based ────────────────────────────
    atr_val  = atr(h, l, c, atr_tp_period)
    tp_long  = (tp_atr_mult * atr_val) / c
    tp_short = (tp_atr_mult * atr_val) / c
    tp_long  = tp_long.clip(lower=0.01, upper=0.20)
    tp_short = tp_short.clip(lower=0.01, upper=0.20)

    # ── Time Stop: rolling exit after time_stop candles ──
    # Implemented via vectorbt's td_stop parameter
    return {
        "entries_long"  : entries_long,
        "entries_short" : entries_short,
        "sl_long"       : sl_long,
        "sl_short"      : sl_short,
        "tp_long"       : tp_long,
        "tp_short"      : tp_short,
        "time_stop"     : time_stop,
    }


def run_backtest(
    df: pd.DataFrame,
    symbol: str,
    params: dict = None,
) -> tuple:
    """Run backtest for both directions. Returns (pf_long, pf_short)."""
    p = params or {}
    sigs = generate_signals(df, **p)
    c = df["close"]

    kwargs = dict(
        fees      = TAKER_FEE,
        slippage  = SLIPPAGE,
        init_cash = INITIAL_CAPITAL,
        size      = RISK_PER_TRADE,
        size_type = "valuepercent",
        upon_opposite_entry = "close",
        td_stop   = sigs["time_stop"],   # time-based exit
    )

    pf_long = vbt.Portfolio.from_signals(
        close   = c,
        entries = sigs["entries_long"],
        exits   = pd.Series(False, index=c.index),
        sl_stop = sigs["sl_long"],
        tp_stop = sigs["tp_long"],
        **kwargs,
    )

    pf_short = vbt.Portfolio.from_signals(
        close          = c,
        entries        = pd.Series(False, index=c.index),
        exits          = pd.Series(False, index=c.index),
        short_entries  = sigs["entries_short"],
        short_exits    = pd.Series(False, index=c.index),
        sl_stop        = sigs["sl_short"],
        tp_stop        = sigs["tp_short"],
        **kwargs,
    )

    return pf_long, pf_short


def optimize(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Grid search over config parameter ranges."""
    p = VOLATILITY_COIL
    results = []

    param_grid = list(product(
        p["opt_atr_ratio"],
        p["opt_bb_period"],
        p["opt_volume_mult"],
        p["opt_tp_multiplier"],
    ))

    logger.info(f"[OPTIMIZE] Volatility Coil — {len(param_grid)} combos on {symbol}")

    for atr_r, bb_p, vol_m, tp_m in param_grid:
        try:
            params = {
                "atr_ratio_thresh": atr_r,
                "bb_period"       : bb_p,
                "vol_mult"        : vol_m,
                "tp_atr_mult"     : tp_m,
            }
            pf_long, pf_short = run_backtest(df, symbol, params)

            for pf, side in [(pf_long, "long"), (pf_short, "short")]:
                stats = pf.stats()
                results.append({
                    "symbol"       : symbol,
                    "side"         : side,
                    "atr_ratio"    : atr_r,
                    "bb_period"    : bb_p,
                    "vol_mult"     : vol_m,
                    "tp_mult"      : tp_m,
                    "total_return" : stats["Total Return [%]"],
                    "sharpe"       : stats["Sharpe Ratio"],
                    "max_drawdown" : stats["Max Drawdown [%]"],
                    "win_rate"     : stats["Win Rate [%]"],
                    "n_trades"     : stats["Total Trades"],
                })
        except Exception as e:
            logger.debug(f"Combo failed: {e}")
            continue

    results_df = pd.DataFrame(results)
    if not results_df.empty:
        results_df = results_df.sort_values("sharpe", ascending=False)

    return results_df
