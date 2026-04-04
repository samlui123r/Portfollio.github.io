"""
=============================================================
 STRATEGY 4: PRE-NFP COMPRESSION TRADE (XAUUSD)
 Asset  : XAUUSDT (Gold)
 TF     : 1H
 Type   : Event-driven breakout (direction-agnostic)
 Signal : Tight range before NFP + first breakout direction
=============================================================
"""

import pandas as pd
import numpy as np
import vectorbt as vbt
import logging
from itertools import product

from data.fetcher import BinanceDataFetcher
from indicators.custom import atr
from config import NFP_COMPRESSION, INITIAL_CAPITAL, TAKER_FEE, SLIPPAGE, RISK_PER_TRADE

logger = logging.getLogger(__name__)


def compute_nfp_windows(
    df: pd.DataFrame,
    nfp_dates: pd.DatetimeIndex,
    pre_nfp_hours: int = NFP_COMPRESSION["pre_nfp_hours"],
    atr_period: int    = NFP_COMPRESSION["atr_period"],
    compress_pct: float= NFP_COMPRESSION["compression_pct"],
    tp_mult: float     = NFP_COMPRESSION["tp_range_multiplier"],
    fill_window: int   = NFP_COMPRESSION["fill_window_minutes"],
) -> pd.DataFrame:
    """
    For each NFP date:
    1. Measure range in prior `pre_nfp_hours` hours
    2. Check if range < compress_pct × ATR(14)
    3. Generate entry at 13:30 UTC as breakout
    4. Return DataFrame with all setup details

    Returns DataFrame with columns:
    nfp_date, valid, compression_range, atr, range_high,
    range_low, direction, entry_price, sl, tp, outcome
    """
    records = []
    atr_series = atr(df["high"], df["low"], df["close"], atr_period)

    for nfp_dt in nfp_dates:
        # ── Get pre-NFP window ────────────────────────────
        window_start = nfp_dt - pd.Timedelta(hours=pre_nfp_hours)
        window_mask  = (df.index >= window_start) & (df.index < nfp_dt)

        if window_mask.sum() < pre_nfp_hours // 2:
            logger.debug(f"Insufficient data for NFP {nfp_dt.date()}")
            continue

        window_df  = df[window_mask]
        range_high = window_df["high"].max()
        range_low  = window_df["low"].min()
        comp_range = range_high - range_low

        # ── Get ATR at time of NFP ────────────────────────
        nfp_idx = df.index.searchsorted(nfp_dt)
        if nfp_idx >= len(df) or nfp_idx == 0:
            continue
        current_atr = atr_series.iloc[nfp_idx - 1]
        atr_threshold = compress_pct * current_atr

        # ── Compression check ─────────────────────────────
        is_compressed = comp_range < atr_threshold

        # ── Get first post-NFP candle direction ───────────
        post_nfp_mask = (
            (df.index >= nfp_dt) &
            (df.index < nfp_dt + pd.Timedelta(minutes=fill_window))
        )
        post_df = df[post_nfp_mask]

        if len(post_df) == 0:
            direction = None
        else:
            first_candle = post_df.iloc[0]
            # Direction determined by first breakout beyond compression range
            if first_candle["high"] > range_high:
                direction = "long"
            elif first_candle["low"] < range_low:
                direction = "short"
            else:
                direction = None  # No breakout within fill window

        # ── Entry / SL / TP ───────────────────────────────
        if direction == "long":
            entry_price = range_high + (range_high * 0.0001)  # 1 pip above
            sl_price    = range_high - comp_range * 0.5       # midpoint
            tp_price    = entry_price + comp_range * tp_mult
        elif direction == "short":
            entry_price = range_low - (range_low * 0.0001)
            sl_price    = range_low + comp_range * 0.5
            tp_price    = entry_price - comp_range * tp_mult
        else:
            entry_price = sl_price = tp_price = np.nan

        # ── Hard exit: 17:00 UTC same day ─────────────────
        hard_exit = nfp_dt.replace(hour=17, minute=0, second=0)

        records.append({
            "nfp_date"     : nfp_dt,
            "valid_setup"  : is_compressed,
            "comp_range"   : comp_range,
            "atr_at_nfp"   : current_atr,
            "range_high"   : range_high,
            "range_low"    : range_low,
            "direction"    : direction,
            "entry_price"  : entry_price,
            "sl_price"     : sl_price,
            "tp_price"     : tp_price,
            "hard_exit"    : hard_exit,
        })

    return pd.DataFrame(records)


def generate_signals(
    df: pd.DataFrame,
    nfp_dates: pd.DatetimeIndex,
    pre_nfp_hours: int  = NFP_COMPRESSION["pre_nfp_hours"],
    compress_pct: float = NFP_COMPRESSION["compression_pct"],
    tp_mult: float      = NFP_COMPRESSION["tp_range_multiplier"],
    fill_window: int    = NFP_COMPRESSION["fill_window_minutes"],
) -> dict:
    """
    Convert NFP setup data into vectorbt signal arrays.

    Returns entry/exit bool series + sl/tp fractions.
    """
    setups = compute_nfp_windows(
        df, nfp_dates, pre_nfp_hours, NFP_COMPRESSION["atr_period"],
        compress_pct, tp_mult, fill_window
    )

    entries_long  = pd.Series(False, index=df.index)
    entries_short = pd.Series(False, index=df.index)
    sl_long       = pd.Series(np.nan, index=df.index)
    sl_short      = pd.Series(np.nan, index=df.index)
    tp_long       = pd.Series(np.nan, index=df.index)
    tp_short      = pd.Series(np.nan, index=df.index)
    hard_exits    = pd.Series(False, index=df.index)

    valid_setups = setups[setups["valid_setup"] & setups["direction"].notna()]

    for _, row in valid_setups.iterrows():
        # Find the closest bar to NFP time
        nfp_dt = row["nfp_date"]
        idx = df.index.searchsorted(nfp_dt)

        if idx >= len(df):
            continue

        bar_price = df["close"].iloc[idx]
        if bar_price == 0 or np.isnan(bar_price):
            continue

        if row["direction"] == "long":
            entries_long.iloc[idx]  = True
            sl_pct = abs(bar_price - row["sl_price"]) / bar_price
            tp_pct = abs(row["tp_price"] - bar_price) / bar_price
            sl_long.iloc[idx] = max(sl_pct, 0.002)
            tp_long.iloc[idx] = max(tp_pct, 0.004)

        elif row["direction"] == "short":
            entries_short.iloc[idx]  = True
            sl_pct = abs(row["sl_price"] - bar_price) / bar_price
            tp_pct = abs(bar_price - row["tp_price"]) / bar_price
            sl_short.iloc[idx] = max(sl_pct, 0.002)
            tp_short.iloc[idx] = max(tp_pct, 0.004)

        # Mark hard exit bar at 17:00 UTC
        exit_idx = df.index.searchsorted(row["hard_exit"])
        if exit_idx < len(df):
            hard_exits.iloc[exit_idx] = True

    # Forward-fill SL/TP within the trade window
    sl_long  = sl_long.ffill().fillna(0.015)
    sl_short = sl_short.ffill().fillna(0.015)
    tp_long  = tp_long.ffill().fillna(0.03)
    tp_short = tp_short.ffill().fillna(0.03)

    return {
        "entries_long"  : entries_long,
        "entries_short" : entries_short,
        "exits"         : hard_exits,
        "sl_long"       : sl_long,
        "sl_short"      : sl_short,
        "tp_long"       : tp_long,
        "tp_short"      : tp_short,
        "setups"        : setups,
    }


def run_backtest(
    df: pd.DataFrame,
    nfp_dates: pd.DatetimeIndex,
    symbol: str = "XAUUSDT",
    params: dict = None,
) -> tuple:
    """Run backtest for both directions on XAUUSD."""
    p = params or {}
    sigs = generate_signals(df, nfp_dates, **p)
    c = df["close"]

    # Max hold: from entry to 17:00 UTC = max ~6 candles (1H bars)
    time_stop = 6

    kwargs = dict(
        fees      = TAKER_FEE,
        slippage  = SLIPPAGE,
        init_cash = INITIAL_CAPITAL,
        size      = RISK_PER_TRADE * 2.5,   # Higher allocation for event trades
        size_type = "valuepercent",
        td_stop   = time_stop,
        upon_opposite_entry = "close",
    )

    pf_long = vbt.Portfolio.from_signals(
        close   = c,
        entries = sigs["entries_long"],
        exits   = sigs["exits"],
        sl_stop = sigs["sl_long"],
        tp_stop = sigs["tp_long"],
        **kwargs,
    )

    pf_short = vbt.Portfolio.from_signals(
        close         = c,
        entries       = pd.Series(False, index=c.index),
        exits         = sigs["exits"],
        short_entries = sigs["entries_short"],
        short_exits   = sigs["exits"],
        sl_stop       = sigs["sl_short"],
        tp_stop       = sigs["tp_short"],
        **kwargs,
    )

    return pf_long, pf_short, sigs["setups"]


def optimize(
    df: pd.DataFrame,
    nfp_dates: pd.DatetimeIndex,
    symbol: str = "XAUUSDT",
) -> pd.DataFrame:
    """Grid search over NFP parameter ranges."""
    p = NFP_COMPRESSION
    results = []

    param_grid = list(product(
        p["opt_pre_nfp_hours"],
        p["opt_compression_pct"],
        p["opt_tp_multiplier"],
    ))

    logger.info(f"[OPTIMIZE] Pre-NFP Compression — {len(param_grid)} combos")

    for pre_h, comp_p, tp_m in param_grid:
        try:
            params = {
                "pre_nfp_hours" : pre_h,
                "compress_pct"  : comp_p,
                "tp_mult"       : tp_m,
            }
            pf_long, pf_short, _ = run_backtest(df, nfp_dates, symbol, params)

            for pf, side in [(pf_long, "long"), (pf_short, "short")]:
                stats = pf.stats()
                results.append({
                    "symbol"         : symbol,
                    "side"           : side,
                    "pre_nfp_hours"  : pre_h,
                    "compress_pct"   : comp_p,
                    "tp_mult"        : tp_m,
                    "total_return"   : stats["Total Return [%]"],
                    "sharpe"         : stats["Sharpe Ratio"],
                    "max_drawdown"   : stats["Max Drawdown [%]"],
                    "win_rate"       : stats["Win Rate [%]"],
                    "n_trades"       : stats["Total Trades"],
                })
        except Exception as e:
            logger.debug(f"Combo failed: {e}")
            continue

    results_df = pd.DataFrame(results)
    if not results_df.empty:
        results_df = results_df.sort_values("sharpe", ascending=False)

    return results_df
