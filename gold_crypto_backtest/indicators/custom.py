"""
=============================================================
 CUSTOM INDICATORS
 All indicator calculations for all 5 strategies.
 Uses pandas/numpy only — no TA-Lib dependency required.
 All functions accept pd.Series, return pd.Series.
=============================================================
"""

import pandas as pd
import numpy as np


# ─── TREND ────────────────────────────────────────────────

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()

def ema_slope(series: pd.Series, period: int, lookback: int = 3) -> pd.Series:
    """Returns slope (positive = trending up)."""
    e = ema(series, period)
    return e - e.shift(lookback)


# ─── VOLATILITY ───────────────────────────────────────────

def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    """Average True Range."""
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def atr_ratio(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    short: int = 7,
    long_: int = 50,
) -> pd.Series:
    """ATR(short) / ATR(long) — compression signal when < 0.4."""
    return atr(high, low, close, short) / atr(high, low, close, long_)


def bollinger_bands(
    close: pd.Series,
    period: int = 20,
    std_dev: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (upper, middle, lower)."""
    middle = close.rolling(period).mean()
    std    = close.rolling(period).std()
    return middle + std_dev * std, middle, middle - std_dev * std


def realized_volatility(close: pd.Series, period: int = 7) -> pd.Series:
    """Rolling annualized realized volatility from log returns."""
    log_ret = np.log(close / close.shift(1))
    return log_ret.rolling(period).std() * np.sqrt(365)


# ─── MOMENTUM ─────────────────────────────────────────────

def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI."""
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def rsi_cross_above(close: pd.Series, period: int, level: float) -> pd.Series:
    """True on bar where RSI crosses above `level` from below."""
    r = rsi(close, period)
    return (r > level) & (r.shift(1) <= level)


def rsi_cross_below(close: pd.Series, period: int, level: float) -> pd.Series:
    """True on bar where RSI crosses below `level` from above."""
    r = rsi(close, period)
    return (r < level) & (r.shift(1) >= level)


# ─── SWING STRUCTURE ──────────────────────────────────────

def swing_lows(low: pd.Series, lookback: int = 20) -> pd.Series:
    """
    Rolling minimum of last `lookback` bars (excluding current bar).
    This is the swing low level that price must sweep through.
    """
    return low.shift(1).rolling(lookback).min()


def swing_highs(high: pd.Series, lookback: int = 20) -> pd.Series:
    """Rolling maximum of last `lookback` bars (excluding current bar)."""
    return high.shift(1).rolling(lookback).max()


def is_sweep_low(
    low: pd.Series,
    close: pd.Series,
    high: pd.Series,
    lookback: int = 20,
    sweep_pct: float = 0.0015,
    wick_rejection: float = 0.70,
) -> pd.Series:
    """
    Detects bullish liquidity sweep (stop-hunt below swing low).
    Returns True when:
    1. Low breaks below rolling swing low by sweep_pct
    2. Close recovers back above swing low
    3. Close is in top wick_rejection% of candle range
    """
    sw_low  = swing_lows(low, lookback)
    candle_range = high - low

    condition_sweep   = low < sw_low * (1 - sweep_pct)
    condition_recover = close > sw_low
    condition_wick    = (close - low) / candle_range.replace(0, np.nan) >= wick_rejection

    return condition_sweep & condition_recover & condition_wick


def is_sweep_high(
    high: pd.Series,
    close: pd.Series,
    low: pd.Series,
    lookback: int = 20,
    sweep_pct: float = 0.0015,
    wick_rejection: float = 0.70,
) -> pd.Series:
    """
    Detects bearish liquidity sweep (stop-hunt above swing high).
    Returns True when:
    1. High breaks above rolling swing high by sweep_pct
    2. Close recovers back below swing high
    3. Close is in bottom wick_rejection% of candle range
    """
    sw_high     = swing_highs(high, lookback)
    candle_range = high - low

    condition_sweep   = high > sw_high * (1 + sweep_pct)
    condition_recover = close < sw_high
    condition_wick    = (high - close) / candle_range.replace(0, np.nan) >= wick_rejection

    return condition_sweep & condition_recover & condition_wick


# ─── VOLUME ───────────────────────────────────────────────

def volume_sma(volume: pd.Series, period: int = 20) -> pd.Series:
    return volume.rolling(period).mean()

def volume_spike(volume: pd.Series, period: int = 20, multiplier: float = 1.5) -> pd.Series:
    """True when current volume > multiplier × rolling average."""
    return volume > volume.rolling(period).mean() * multiplier


# ─── SESSION FILTERS ──────────────────────────────────────

def london_open_filter(index: pd.DatetimeIndex) -> pd.Series:
    """True during London session: 07:00–12:00 UTC."""
    h = index.hour
    return pd.Series((h >= 7) & (h < 12), index=index)

def ny_open_filter(index: pd.DatetimeIndex) -> pd.Series:
    """True during NY open window: 13:00–15:00 UTC."""
    h = index.hour
    return pd.Series((h >= 13) & (h < 15), index=index)

def asian_session_filter(index: pd.DatetimeIndex) -> pd.Series:
    """True during Asian session: 00:00–06:00 UTC."""
    h = index.hour
    return pd.Series(h < 6, index=index)

def no_weekend_filter(index: pd.DatetimeIndex) -> pd.Series:
    """True when NOT weekend (Fri 20:00 UTC – Sun 18:00 UTC)."""
    dow = index.dayofweek   # 0=Mon, 6=Sun
    h   = index.hour
    is_weekend = (
        ((dow == 4) & (h >= 20)) |   # Friday after 20:00
        (dow == 5) |                  # All Saturday
        ((dow == 6) & (h < 18))       # Sunday before 18:00
    )
    return pd.Series(~is_weekend, index=index)


# ─── DONCHIAN CHANNEL ─────────────────────────────────────

def donchian_high(high: pd.Series, period: int = 20) -> pd.Series:
    return high.rolling(period).max()

def donchian_low(low: pd.Series, period: int = 20) -> pd.Series:
    return low.rolling(period).min()

def donchian_breakout_long(
    close: pd.Series,
    high: pd.Series,
    period: int = 20,
) -> pd.Series:
    """True when close breaks above Donchian high."""
    dc_high = high.shift(1).rolling(period).max()
    return close > dc_high

def donchian_breakout_short(
    close: pd.Series,
    low: pd.Series,
    period: int = 20,
) -> pd.Series:
    """True when close breaks below Donchian low."""
    dc_low = low.shift(1).rolling(period).min()
    return close < dc_low


# ─── VWAP ─────────────────────────────────────────────────

def rolling_vwap(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    period: int = 20,
) -> pd.Series:
    """Rolling VWAP over `period` bars."""
    typical_price = (high + low + close) / 3
    tp_vol = typical_price * volume
    return tp_vol.rolling(period).sum() / volume.rolling(period).sum()


# ─── FUNDING RATE INDICATORS ──────────────────────────────

def funding_ma(funding: pd.Series, period: int = 9) -> pd.Series:
    """Simple moving average of funding rate (period in 8H intervals)."""
    return funding.rolling(period).mean()

def funding_trend_up(funding: pd.Series, ma_period: int = 9, n_periods: int = 5) -> pd.Series:
    """True when funding MA has been rising for n consecutive periods."""
    f_ma = funding_ma(funding, ma_period)
    slope = f_ma - f_ma.shift(1)
    # Rolling sum of (slope > 0) must equal n_periods
    return slope.rolling(n_periods).apply(lambda x: (x > 0).all(), raw=True).astype(bool)

def funding_extreme_long(funding: pd.Series, threshold: float = 0.0008) -> pd.Series:
    """True when funding rate exceeds threshold (crowd over-levered long)."""
    return funding > threshold

def funding_extreme_short(funding: pd.Series, threshold: float = 0.0008) -> pd.Series:
    """True when funding rate is below -threshold (crowd over-levered short)."""
    return funding < -threshold


# ─── OPEN INTEREST DIVERGENCE ─────────────────────────────

def oi_divergence_bearish(
    close: pd.Series,
    oi_proxy: pd.Series,
    lookback: int = 3,
) -> pd.Series:
    """
    Bearish divergence: price makes higher high but OI is flat/declining.
    Price up over lookback days, OI change < 2%.
    """
    price_up = close > close.shift(lookback)
    oi_flat  = (oi_proxy - oi_proxy.shift(lookback)) / oi_proxy.shift(lookback) < 0.02
    return price_up & oi_flat

def oi_divergence_bullish(
    close: pd.Series,
    oi_proxy: pd.Series,
    lookback: int = 3,
) -> pd.Series:
    """
    Bullish divergence: price makes lower low but OI is flat/declining.
    """
    price_down = close < close.shift(lookback)
    oi_flat    = (oi_proxy - oi_proxy.shift(lookback)) / oi_proxy.shift(lookback) < 0.02
    return price_down & oi_flat


# ─── MOMENTUM CRACK ───────────────────────────────────────

def bearish_momentum_crack(close: pd.Series, high: pd.Series) -> pd.Series:
    """
    Price closes below prior candle's low — momentum failure signal.
    Used in funding exhaustion as final entry trigger.
    """
    return close < close.shift(1)

def bullish_momentum_crack(close: pd.Series, low: pd.Series) -> pd.Series:
    """Price closes above prior candle's high."""
    return close > close.shift(1)


# ─── COMPRESSION RANGE ────────────────────────────────────

def rolling_range_pct(
    high: pd.Series,
    low: pd.Series,
    period: int,
) -> pd.Series:
    """
    Returns (rolling_high - rolling_low) / rolling_low as % range.
    Used for session range calculations.
    """
    r_high = high.rolling(period).max()
    r_low  = low.rolling(period).min()
    return (r_high - r_low) / r_low


# ─── MAX-PAIN PROXY ───────────────────────────────────────

def max_pain_proxy(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    period: int = 30,
) -> pd.Series:
    """
    Proxy for options max-pain level using volume-weighted price over period.
    In absence of real options chain data, VWAP is the best approximation.
    """
    return rolling_vwap(high, low, close, volume, period)

def distance_from_proxy(close: pd.Series, proxy: pd.Series) -> pd.Series:
    """Signed % distance: positive = above proxy."""
    return (close - proxy) / proxy
