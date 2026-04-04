"""
=============================================================
 STRATEGY 3: FUNDING RATE EXHAUSTION REVERSAL
 Asset  : BTC, ETH, SOL (USDT-M Perpetuals)
 TF     : 4H price | 8H funding (resampled to match)
 Type   : Sentiment/leverage fade
 Signal : Extreme funding + OI divergence + momentum crack
=============================================================
"""

import pandas as pd
import numpy as np
import vectorbt as vbt
import logging
from itertools import product

from indicators.custom import (
    funding_extreme_long,
    funding_extreme_short,
    funding_trend_up,
    funding_ma,
    oi_divergence_bearish,
    oi_divergence_bullish,
    bearish_momentum_crack,
    bullish_momentum_crack,
    atr,
    swing_highs,
    swing_lows,
)
from config import FUNDING_EXHAUSTION, INITIAL_CAPITAL, TAKER_FEE, SLIPPAGE, RISK_PER_TRADE

logger = logging.getLogger(__name__)


def align_funding_to_ohlcv(
    funding: pd.Series,
    ohlcv_index: pd.DatetimeIndex,
) -> pd.Series:
    """
    Aligns 8H funding rate series to 4H OHLCV index via forward-fill.
    """
    # Reindex to 4H OHLCV timestamps, forward-fill
    aligned = funding.reindex(ohlcv_index, method="ffill")
    return aligned


def generate_signals(
    df: pd.DataFrame,
    funding: pd.Series,
    oi_proxy: pd.Series,
    funding_threshold: float  = FUNDING_EXHAUSTION["funding_threshold"],
    funding_ma_period: int    = FUNDING_EXHAUSTION["funding_ma_period"],
    funding_trend_n: int      = FUNDING_EXHAUSTION["funding_trend_periods"],
    oi_lookback: int          = FUNDING_EXHAUSTION["oi_lookback"],
    price_lookback: int       = FUNDING_EXHAUSTION["price_lookback"],
    tp_atr_mult: float        = FUNDING_EXHAUSTION["tp_atr_multiplier"],
    sl_lookback: int          = FUNDING_EXHAUSTION["sl_swing_lookback"],
) -> dict:
    """
    SHORT entry when:
      1. Funding rate > threshold (extreme longs)
      2. Funding MA trending up for n consecutive 8H periods
      3. OI divergence bearish (price up, OI flat)
      4. Bearish momentum crack (close < prev close) on 4H

    LONG entry (squeeze reversal) when:
      1. Funding rate < -threshold (extreme shorts)
      2. Funding MA trending down
      3. OI divergence bullish (price down, OI flat)
      4. Bullish momentum crack (close > prev close)
    """
    h = df["high"]
    l = df["low"]
    c = df["close"]

    # ── Align funding to OHLCV index ─────────────────────
    funding_aligned = align_funding_to_ohlcv(funding, df.index)

    # ── Funding conditions ────────────────────────────────
    extreme_long  = funding_extreme_long(funding_aligned, funding_threshold)
    extreme_short = funding_extreme_short(funding_aligned, funding_threshold)

    # Funding trend (in original 8H periods, then reindex)
    f_ma    = funding_ma(funding_aligned, funding_ma_period * 3)  # 3 × 8H per day
    f_trend_up   = (f_ma - f_ma.shift(1)) > 0
    f_trend_down = (f_ma - f_ma.shift(1)) < 0

    f_trend_up_n   = f_trend_up.rolling(funding_trend_n).apply(lambda x: x.all(), raw=True).fillna(False).astype(bool)
    f_trend_down_n = f_trend_down.rolling(funding_trend_n).apply(lambda x: x.all(), raw=True).fillna(False).astype(bool)

    # ── OI divergence (proxy-based) ───────────────────────
    # Align OI proxy to same index
    oi_aligned = oi_proxy.reindex(df.index, method="ffill")
    oi_div_bear = oi_divergence_bearish(c, oi_aligned, oi_lookback)
    oi_div_bull = oi_divergence_bullish(c, oi_aligned, oi_lookback)

    # ── Momentum crack ────────────────────────────────────
    mom_crack_bear = bearish_momentum_crack(c, h)   # close < prev close
    mom_crack_bull = bullish_momentum_crack(c, l)    # close > prev close

    # ── Combined entries ──────────────────────────────────
    entries_short = (
        extreme_long      &   # Condition 1: over-leveraged longs
        f_trend_up_n      &   # Condition 2: funding rising
        oi_div_bear       &   # Condition 3: OI divergence
        mom_crack_bear        # Condition 4: momentum crack
    )

    entries_long = (
        extreme_short     &   # Condition 1: over-leveraged shorts
        f_trend_down_n    &   # Condition 2: funding falling
        oi_div_bull       &   # Condition 3: OI divergence
        mom_crack_bull        # Condition 4: momentum crack
    )

    # ── Stop Loss ─────────────────────────────────────────
    atr_val     = atr(h, l, c, 14)
    sw_high     = swing_highs(h, sl_lookback)
    sw_low      = swing_lows(l, sl_lookback)

    # SL for short: above most recent swing high
    sl_short = (sw_high - c) / c
    sl_short = sl_short.clip(lower=0.01, upper=0.10)

    # SL for long: below most recent swing low
    sl_long  = (c - sw_low) / c
    sl_long  = sl_long.clip(lower=0.01, upper=0.10)

    # ── Take Profit: ATR-based ────────────────────────────
    tp_short = (tp_atr_mult * atr_val) / c
    tp_long  = (tp_atr_mult * atr_val) / c
    tp_short = tp_short.clip(lower=0.02, upper=0.25)
    tp_long  = tp_long.clip(lower=0.02, upper=0.25)

    return {
        "entries_long"  : entries_long.fillna(False),
        "entries_short" : entries_short.fillna(False),
        "sl_long"       : sl_long,
        "sl_short"      : sl_short,
        "tp_long"       : tp_long,
        "tp_short"      : tp_short,
    }


def run_backtest(
    df: pd.DataFrame,
    funding: pd.Series,
    oi_proxy: pd.Series,
    symbol: str,
    params: dict = None,
) -> tuple:
    """Run backtest for both long and short sides."""
    p = params or {}
    sigs = generate_signals(df, funding, oi_proxy, **p)
    c = df["close"]

    # Time stop: 48 hours on 4H chart = 12 candles
    time_stop_candles = FUNDING_EXHAUSTION["time_stop_hours"] // 4

    kwargs = dict(
        fees      = TAKER_FEE,
        slippage  = SLIPPAGE,
        init_cash = INITIAL_CAPITAL,
        size      = RISK_PER_TRADE,
        size_type = "valuepercent",
        td_stop   = time_stop_candles,
        upon_opposite_entry = "close",
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
        close         = c,
        entries       = pd.Series(False, index=c.index),
        exits         = pd.Series(False, index=c.index),
        short_entries = sigs["entries_short"],
        short_exits   = pd.Series(False, index=c.index),
        sl_stop       = sigs["sl_short"],
        tp_stop       = sigs["tp_short"],
        **kwargs,
    )

    return pf_long, pf_short


def optimize(
    df: pd.DataFrame,
    funding: pd.Series,
    oi_proxy: pd.Series,
    symbol: str,
) -> pd.DataFrame:
    """Grid search over config parameter ranges."""
    p = FUNDING_EXHAUSTION
    results = []

    param_grid = list(product(
        p["opt_funding_threshold"],
        p["opt_trend_periods"],
        p["opt_oi_lookback"],
    ))

    logger.info(f"[OPTIMIZE] Funding Exhaustion — {len(param_grid)} combos on {symbol}")

    for f_thresh, trend_n, oi_lb in param_grid:
        try:
            params = {
                "funding_threshold" : f_thresh,
                "funding_trend_n"   : trend_n,
                "oi_lookback"       : oi_lb,
            }
            pf_long, pf_short = run_backtest(df, funding, oi_proxy, symbol, params)

            for pf, side in [(pf_long, "long"), (pf_short, "short")]:
                stats = pf.stats()
                results.append({
                    "symbol"            : symbol,
                    "side"              : side,
                    "funding_threshold" : f_thresh,
                    "trend_periods"     : trend_n,
                    "oi_lookback"       : oi_lb,
                    "total_return"      : stats["Total Return [%]"],
                    "sharpe"            : stats["Sharpe Ratio"],
                    "max_drawdown"      : stats["Max Drawdown [%]"],
                    "win_rate"          : stats["Win Rate [%]"],
                    "n_trades"          : stats["Total Trades"],
                })
        except Exception as e:
            logger.debug(f"Combo failed: {e}")
            continue

    results_df = pd.DataFrame(results)
    if not results_df.empty:
        results_df = results_df.sort_values("sharpe", ascending=False)

    return results_df
