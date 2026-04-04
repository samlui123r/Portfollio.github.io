"""
=============================================================
 STRATEGY 1: LIQUIDITY SWEEP REVERSAL
 Asset  : BTC, ETH, XAUUSD
 TF     : 15M (crypto) / 1H (XAUUSD)
 Type   : Stop-hunt fade
 Signal : Sweep below swing low + wick rejection + RSI < 35
=============================================================
"""

import pandas as pd
import numpy as np
import vectorbt as vbt
import logging
from itertools import product

from indicators.custom import (
    is_sweep_low,
    is_sweep_high,
    swing_highs,
    swing_lows,
    rsi,
    atr,
    no_weekend_filter,
)
from config import LIQUIDITY_SWEEP, INITIAL_CAPITAL, TAKER_FEE, SLIPPAGE, RISK_PER_TRADE

logger = logging.getLogger(__name__)


def generate_signals(
    df: pd.DataFrame,
    swing_lookback: int   = LIQUIDITY_SWEEP["swing_lookback"],
    sweep_pct: float      = LIQUIDITY_SWEEP["sweep_threshold"],
    wick_rejection: float = LIQUIDITY_SWEEP["wick_rejection_pct"],
    rsi_period: int       = LIQUIDITY_SWEEP["rsi_period"],
    rsi_thresh: float     = LIQUIDITY_SWEEP["rsi_threshold"],
    sl_buffer: float      = LIQUIDITY_SWEEP["sl_buffer"],
    tp2_mult: float       = LIQUIDITY_SWEEP["tp2_multiplier"],
    tp1_lookback: int     = LIQUIDITY_SWEEP["tp1_swing_lookback"],
) -> dict:
    """
    Generate entry/exit signals and stop/TP levels.

    Entry (long):
      - Candle sweeps below swing low by sweep_pct
      - Same candle closes back above swing low
      - Close in top wick_rejection% of range
      - RSI < rsi_thresh at sweep
      - No weekend (crypto only)

    Returns dict with:
      entries, exits (pd.Series bool)
      sl_stop, tp_stop (pd.Series float — fraction of price)
    """
    o = df["open"]
    h = df["high"]
    l = df["low"]
    c = df["close"]

    # ── Core sweep signal ─────────────────────────────────
    sweep_long  = is_sweep_low(l, c, h, swing_lookback, sweep_pct, wick_rejection)
    sweep_short = is_sweep_high(h, c, l, swing_lookback, sweep_pct, wick_rejection)

    # ── RSI filter ────────────────────────────────────────
    r = rsi(c, rsi_period)
    rsi_long  = r < rsi_thresh
    rsi_short = r > (100 - rsi_thresh)

    # ── Weekend filter (skips low-liquidity crypto periods) ──
    no_weekend = no_weekend_filter(df.index)

    # ── Combined entry ────────────────────────────────────
    entries_long  = sweep_long  & rsi_long  & no_weekend
    entries_short = sweep_short & rsi_short & no_weekend

    # ── Stop Loss: just beyond sweep wick ─────────────────
    sw_low  = swing_lows(l, swing_lookback)
    sw_high = swing_highs(h, swing_lookback)

    sl_long  = (c - (l * (1 - sl_buffer))) / c     # fraction below close
    sl_short = ((h * (1 + sl_buffer)) - c) / c

    # ── TP1: Prior swing high (for long), prior swing low (for short) ──
    tp1_long  = (swing_highs(h, tp1_lookback) - c) / c
    tp1_short = (c - swing_lows(l, tp1_lookback)) / c

    # ── TP2: 2x sweep distance from entry ─────────────────
    sweep_distance_long  = (sw_low - l).abs() / c
    sweep_distance_short = (h - sw_high).abs() / c
    tp2_long  = sweep_distance_long  * tp2_mult
    tp2_short = sweep_distance_short * tp2_mult

    # Use TP1 as primary exit (more conservative)
    tp_long  = tp1_long.clip(lower=0.002, upper=0.10)
    tp_short = tp1_short.clip(lower=0.002, upper=0.10)
    sl_long  = sl_long.clip(lower=0.001, upper=0.05)
    sl_short = sl_short.clip(lower=0.001, upper=0.05)

    return {
        "entries_long"  : entries_long,
        "entries_short" : entries_short,
        "sl_long"       : sl_long,
        "sl_short"      : sl_short,
        "tp_long"       : tp_long,
        "tp_short"      : tp_short,
    }


def run_backtest(
    df: pd.DataFrame,
    symbol: str,
    params: dict = None,
    direction: str = "both",     # "long", "short", or "both"
) -> vbt.Portfolio:
    """
    Run vectorbt backtest for Liquidity Sweep strategy.
    Returns Portfolio object.
    """
    p = params or {}
    sigs = generate_signals(df, **p)

    c = df["close"]

    kwargs_base = dict(
        fees      = TAKER_FEE,
        slippage  = SLIPPAGE,
        freq      = df.index.freq or pd.infer_freq(df.index),
        init_cash = INITIAL_CAPITAL,
    )

    if direction in ("long", "both"):
        pf_long = vbt.Portfolio.from_signals(
            close        = c,
            entries      = sigs["entries_long"],
            exits        = pd.Series(False, index=c.index),
            sl_stop      = sigs["sl_long"],
            tp_stop      = sigs["tp_long"],
            size         = RISK_PER_TRADE,
            size_type    = "valuepercent",
            upon_opposite_entry = "close",
            **kwargs_base,
        )
    if direction in ("short", "both"):
        pf_short = vbt.Portfolio.from_signals(
            close        = c,
            entries      = sigs["entries_short"],
            exits        = pd.Series(False, index=c.index),
            short_entries= sigs["entries_short"],
            sl_stop      = sigs["sl_short"],
            tp_stop      = sigs["tp_short"],
            size         = RISK_PER_TRADE,
            size_type    = "valuepercent",
            upon_opposite_entry = "close",
            **kwargs_base,
        )

    # For "both", combine portfolios
    if direction == "both":
        return pf_long, pf_short
    elif direction == "long":
        return pf_long
    else:
        return pf_short


def optimize(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """
    Grid search over parameter ranges defined in config.
    Returns DataFrame sorted by Sharpe ratio.
    """
    p = LIQUIDITY_SWEEP
    results = []

    param_grid = list(product(
        p["opt_swing_lookback"],
        p["opt_sweep_threshold"],
        p["opt_rsi_threshold"],
        p["opt_wick_rejection"],
    ))

    logger.info(f"[OPTIMIZE] Liquidity Sweep — {len(param_grid)} param combos on {symbol}")

    for swing_lb, sweep_t, rsi_t, wick_r in param_grid:
        try:
            params = {
                "swing_lookback"  : swing_lb,
                "sweep_pct"       : sweep_t,
                "rsi_thresh"      : rsi_t,
                "wick_rejection"  : wick_r,
            }
            pf_long, pf_short = run_backtest(df, symbol, params, direction="both")

            for pf, side in [(pf_long, "long"), (pf_short, "short")]:
                stats = pf.stats()
                results.append({
                    "symbol"         : symbol,
                    "side"           : side,
                    "swing_lookback" : swing_lb,
                    "sweep_threshold": sweep_t,
                    "rsi_threshold"  : rsi_t,
                    "wick_rejection" : wick_r,
                    "total_return"   : stats["Total Return [%]"],
                    "sharpe"         : stats["Sharpe Ratio"],
                    "max_drawdown"   : stats["Max Drawdown [%]"],
                    "win_rate"       : stats["Win Rate [%]"],
                    "n_trades"       : stats["Total Trades"],
                    "profit_factor"  : stats.get("Profit Factor", np.nan),
                    "expectancy"     : stats.get("Expectancy", np.nan),
                })
        except Exception as e:
            logger.debug(f"Combo failed: {e}")
            continue

    results_df = pd.DataFrame(results)
    if not results_df.empty:
        results_df = results_df.sort_values("sharpe", ascending=False)

    return results_df
