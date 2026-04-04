"""
=============================================================
 STRATEGY 5: GAMMA SQUEEZE ANTICIPATION (PROXY-BASED)
 Asset  : BTCUSDT
 TF     : 4H
 Type   : Options dealer hedging flow proxy
 Note   : Real Deribit OI unavailable historically.
          Uses 30-day VWAP as max-pain proxy.
          Backtests validate the mean-reversion mechanic.
          Live version connects to Deribit API directly.
=============================================================
"""

import pandas as pd
import numpy as np
import vectorbt as vbt
import logging
from itertools import product
from datetime import timedelta

from data.fetcher import BinanceDataFetcher
from indicators.custom import (
    rolling_vwap,
    max_pain_proxy,
    distance_from_proxy,
    atr,
    ema,
)
from config import GAMMA_SQUEEZE, INITIAL_CAPITAL, TAKER_FEE, SLIPPAGE, RISK_PER_TRADE

logger = logging.getLogger(__name__)


def get_pre_expiry_mask(
    index: pd.DatetimeIndex,
    expiry_dates: pd.DatetimeIndex,
    pre_expiry_hours: int = GAMMA_SQUEEZE["pre_expiry_hours"],
) -> pd.Series:
    """
    Returns boolean Series: True for bars within pre_expiry_hours before any expiry.
    """
    mask = pd.Series(False, index=index)
    for expiry_dt in expiry_dates:
        window_start = expiry_dt - pd.Timedelta(hours=pre_expiry_hours)
        window_mask  = (index >= window_start) & (index < expiry_dt)
        mask = mask | pd.Series(window_mask, index=index)
    return mask


def generate_signals(
    df: pd.DataFrame,
    expiry_dates: pd.DatetimeIndex,
    pre_expiry_hours: int    = GAMMA_SQUEEZE["pre_expiry_hours"],
    proxy_period: int        = GAMMA_SQUEEZE["max_pain_proxy_period"],
    distance_thresh: float   = GAMMA_SQUEEZE["distance_threshold"],
    momentum_candles: int    = GAMMA_SQUEEZE["momentum_candles"],
    sl_pct: float            = GAMMA_SQUEEZE["sl_distance_pct"],
) -> dict:
    """
    Logic:
    1. Only active within pre_expiry_hours before monthly expiry
    2. Compute 30-day VWAP as max-pain proxy
    3. If price > distance_thresh above proxy: enter short (mean-revert down)
    4. If price > distance_thresh below proxy: enter long (mean-revert up)
    5. Confirm: price momentum for `momentum_candles` toward proxy
    6. Exit: price reaches within 0.5% of proxy OR SL hit

    Returns signal arrays for vectorbt.
    """
    h = df["high"]
    l = df["low"]
    c = df["close"]
    v = df["volume"]

    # ── Max-pain proxy (30-day rolling VWAP) ─────────────
    proxy = max_pain_proxy(h, l, c, v, proxy_period)
    dist  = distance_from_proxy(c, proxy)   # positive = above proxy

    # ── Pre-expiry filter ─────────────────────────────────
    pre_expiry = get_pre_expiry_mask(df.index, expiry_dates, pre_expiry_hours)

    # ── Distance conditions ───────────────────────────────
    above_proxy = dist > distance_thresh     # price too far above → short
    below_proxy = dist < -distance_thresh    # price too far below → long

    # ── Momentum toward proxy ─────────────────────────────
    # For short: price must be declining toward proxy (closes falling)
    # For long:  price must be rising toward proxy (closes rising)
    mom_short = (c < c.shift(1)).rolling(momentum_candles).apply(
        lambda x: x.all(), raw=True
    ).fillna(False).astype(bool)

    mom_long  = (c > c.shift(1)).rolling(momentum_candles).apply(
        lambda x: x.all(), raw=True
    ).fillna(False).astype(bool)

    # ── Combined entries ──────────────────────────────────
    entries_short = pre_expiry & above_proxy & mom_short
    entries_long  = pre_expiry & below_proxy & mom_long

    # ── Exit: price returns to proxy (±0.5%) ─────────────
    near_proxy = dist.abs() < 0.005
    exits_on_proxy = near_proxy

    # ── Stop Loss ─────────────────────────────────────────
    # SL: if price moves sl_pct further AWAY from proxy
    atr_val   = atr(h, l, c, 14)
    sl_series = pd.Series(sl_pct, index=df.index)  # fixed % SL

    # Clip to reasonable range
    sl_series = sl_series.clip(lower=0.015, upper=0.06)

    return {
        "entries_long"   : entries_long.fillna(False),
        "entries_short"  : entries_short.fillna(False),
        "exits"          : exits_on_proxy.fillna(False),
        "sl"             : sl_series,
        "proxy"          : proxy,
        "distance"       : dist,
        "pre_expiry"     : pre_expiry,
    }


def run_backtest(
    df: pd.DataFrame,
    expiry_dates: pd.DatetimeIndex,
    symbol: str = "BTCUSDT",
    params: dict = None,
) -> tuple:
    """Run backtest for both long and short sides."""
    p = params or {}
    sigs = generate_signals(df, expiry_dates, **p)
    c = df["close"]

    # Time stop: pre_expiry_hours / 4 (4H bars)
    pre_h = p.get("pre_expiry_hours", GAMMA_SQUEEZE["pre_expiry_hours"])
    time_stop_candles = pre_h // 4

    # Hard exit at expiry: mark expiry bars as exits
    expiry_exits = pd.Series(False, index=df.index)
    for exp_dt in expiry_dates:
        exp_idx = df.index.searchsorted(exp_dt)
        if exp_idx < len(df):
            expiry_exits.iloc[exp_idx] = True

    combined_exits = sigs["exits"] | expiry_exits

    kwargs = dict(
        fees      = TAKER_FEE,
        slippage  = SLIPPAGE,
        init_cash = INITIAL_CAPITAL,
        size      = RISK_PER_TRADE * 1.5,
        size_type = "valuepercent",
        td_stop   = time_stop_candles,
        upon_opposite_entry = "close",
    )

    pf_long = vbt.Portfolio.from_signals(
        close   = c,
        entries = sigs["entries_long"],
        exits   = combined_exits,
        sl_stop = sigs["sl"],
        **kwargs,
    )

    pf_short = vbt.Portfolio.from_signals(
        close         = c,
        entries       = pd.Series(False, index=c.index),
        exits         = combined_exits,
        short_entries = sigs["entries_short"],
        short_exits   = combined_exits,
        sl_stop       = sigs["sl"],
        **kwargs,
    )

    return pf_long, pf_short, sigs


def optimize(
    df: pd.DataFrame,
    expiry_dates: pd.DatetimeIndex,
    symbol: str = "BTCUSDT",
) -> pd.DataFrame:
    """Grid search over gamma squeeze parameter ranges."""
    p = GAMMA_SQUEEZE
    results = []

    param_grid = list(product(
        p["opt_distance_threshold"],
        p["opt_pre_expiry_hours"],
        p["opt_momentum_candles"],
    ))

    logger.info(f"[OPTIMIZE] Gamma Squeeze — {len(param_grid)} combos on {symbol}")

    for dist_t, pre_h, mom_c in param_grid:
        try:
            params = {
                "distance_thresh"   : dist_t,
                "pre_expiry_hours"  : pre_h,
                "momentum_candles"  : mom_c,
            }
            pf_long, pf_short, _ = run_backtest(df, expiry_dates, symbol, params)

            for pf, side in [(pf_long, "long"), (pf_short, "short")]:
                stats = pf.stats()
                results.append({
                    "symbol"           : symbol,
                    "side"             : side,
                    "distance_thresh"  : dist_t,
                    "pre_expiry_hours" : pre_h,
                    "momentum_candles" : mom_c,
                    "total_return"     : stats["Total Return [%]"],
                    "sharpe"           : stats["Sharpe Ratio"],
                    "max_drawdown"     : stats["Max Drawdown [%]"],
                    "win_rate"         : stats["Win Rate [%]"],
                    "n_trades"         : stats["Total Trades"],
                })
        except Exception as e:
            logger.debug(f"Combo failed: {e}")
            continue

    results_df = pd.DataFrame(results)
    if not results_df.empty:
        results_df = results_df.sort_values("sharpe", ascending=False)

    return results_df
