"""
=============================================================
 DATA FETCHER
 Pulls OHLCV + funding rates from Binance via ccxt
 Caches locally so you don't re-download on every run
=============================================================
"""

import ccxt
import pandas as pd
import numpy as np
import os
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)
CACHE_DIR = Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class BinanceDataFetcher:
    """
    Fetches and caches OHLCV + funding rate data from Binance.
    Uses Binance USDT-M Futures for all crypto pairs.
    Uses Binance spot for XAUUSDT (gold).
    """

    def __init__(self):
        self.futures = ccxt.binance({
            "options": {"defaultType": "future"},
            "enableRateLimit": True,
        })
        self.spot = ccxt.binance({
            "options": {"defaultType": "spot"},
            "enableRateLimit": True,
        })

    # ── OHLCV ─────────────────────────────────────────────

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: str,
        end: str,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Returns DataFrame with columns:
        open, high, low, close, volume
        Indexed by UTC datetime.
        """
        cache_file = CACHE_DIR / f"{symbol}_{timeframe}_{start}_{end}.parquet"

        if use_cache and cache_file.exists():
            logger.info(f"[CACHE HIT] {symbol} {timeframe}")
            return pd.read_parquet(cache_file)

        logger.info(f"[FETCHING] {symbol} {timeframe} from Binance...")

        is_gold = "XAU" in symbol
        exchange = self.spot if is_gold else self.futures

        since_ms = int(datetime.strptime(start, "%Y-%m-%d").timestamp() * 1000)
        end_ms   = int(datetime.strptime(end,   "%Y-%m-%d").timestamp() * 1000)

        all_candles = []
        while since_ms < end_ms:
            try:
                candles = exchange.fetch_ohlcv(
                    symbol, timeframe, since=since_ms, limit=1000
                )
            except ccxt.RateLimitExceeded:
                logger.warning("Rate limit hit — sleeping 10s")
                time.sleep(10)
                continue
            except Exception as e:
                logger.error(f"Error fetching {symbol}: {e}")
                break

            if not candles:
                break

            all_candles.extend(candles)
            since_ms = candles[-1][0] + 1
            time.sleep(exchange.rateLimit / 1000)

        df = pd.DataFrame(
            all_candles,
            columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.set_index("timestamp", inplace=True)
        df = df[df.index < pd.Timestamp(end, tz="UTC")]
        df = df[~df.index.duplicated()].sort_index()

        if use_cache:
            df.to_parquet(cache_file)
            logger.info(f"[CACHED] {cache_file}")

        return df

    # ── FUNDING RATES ─────────────────────────────────────

    def fetch_funding_rates(
        self,
        symbol: str,
        start: str,
        end: str,
        use_cache: bool = True,
    ) -> pd.Series:
        """
        Returns hourly funding rate Series indexed by UTC datetime.
        Binance pays funding every 8 hours (00:00, 08:00, 16:00 UTC).
        Values are interpolated to hourly for alignment with OHLCV.
        """
        cache_file = CACHE_DIR / f"funding_{symbol}_{start}_{end}.parquet"

        if use_cache and cache_file.exists():
            logger.info(f"[CACHE HIT] Funding {symbol}")
            return pd.read_parquet(cache_file)["funding_rate"]

        logger.info(f"[FETCHING] Funding rates {symbol}...")

        since_ms = int(datetime.strptime(start, "%Y-%m-%d").timestamp() * 1000)
        end_ms   = int(datetime.strptime(end,   "%Y-%m-%d").timestamp() * 1000)

        all_rates = []
        while since_ms < end_ms:
            try:
                history = self.futures.fetch_funding_rate_history(
                    symbol, since=since_ms, limit=1000
                )
            except Exception as e:
                logger.error(f"Funding fetch error: {e}")
                break

            if not history:
                break

            all_rates.extend(history)
            since_ms = history[-1]["timestamp"] + 1
            time.sleep(self.futures.rateLimit / 1000)

        if not all_rates:
            logger.warning(f"No funding data for {symbol} — returning zeros")
            idx = pd.date_range(start, end, freq="1h", tz="UTC")
            return pd.Series(0.0, index=idx, name="funding_rate")

        df = pd.DataFrame(all_rates)[["timestamp", "fundingRate"]]
        df.columns = ["timestamp", "funding_rate"]
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.set_index("timestamp", inplace=True)
        df = df[~df.index.duplicated()].sort_index()

        # Resample to 1H via forward-fill (funding rate holds for 8H)
        df_hourly = df.resample("1h").ffill()
        df_hourly.to_parquet(cache_file)

        return df_hourly["funding_rate"]

    # ── OPEN INTEREST (PROXY) ─────────────────────────────

    def fetch_open_interest_proxy(
        self,
        symbol: str,
        timeframe: str,
        start: str,
        end: str,
    ) -> pd.Series:
        """
        Binance historical OI endpoint is limited.
        We use volume * close as an OI proxy (common in research).
        Returns proxy OI Series aligned to OHLCV index.
        """
        df = self.fetch_ohlcv(symbol, timeframe, start, end)
        oi_proxy = df["volume"] * df["close"]
        oi_proxy.name = "oi_proxy"
        return oi_proxy

    # ── NFP DATES ─────────────────────────────────────────

    @staticmethod
    def get_nfp_dates(start: str, end: str) -> pd.DatetimeIndex:
        """
        Returns all NFP release dates (first Friday of each month)
        between start and end, in UTC at 13:30.
        """
        start_dt = pd.Timestamp(start, tz="UTC")
        end_dt   = pd.Timestamp(end,   tz="UTC")

        nfp_dates = []
        current = start_dt.replace(day=1)

        while current <= end_dt:
            # Find first Friday of month
            day = current
            while day.weekday() != 4:  # 4 = Friday
                day += timedelta(days=1)
            nfp_dt = day.replace(hour=13, minute=30, second=0)
            if start_dt <= nfp_dt <= end_dt:
                nfp_dates.append(nfp_dt)
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)

        return pd.DatetimeIndex(nfp_dates)

    # ── MONTHLY EXPIRY DATES ──────────────────────────────

    @staticmethod
    def get_monthly_expiry_dates(start: str, end: str) -> pd.DatetimeIndex:
        """
        Deribit monthly options expire on last Friday of each month at 08:00 UTC.
        Returns those dates between start and end.
        """
        start_dt = pd.Timestamp(start, tz="UTC")
        end_dt   = pd.Timestamp(end,   tz="UTC")

        expiry_dates = []
        current = start_dt.replace(day=1)

        while current <= end_dt:
            # Last day of month
            if current.month == 12:
                last_day = current.replace(year=current.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                last_day = current.replace(month=current.month + 1, day=1) - timedelta(days=1)

            # Walk back to last Friday
            day = last_day
            while day.weekday() != 4:
                day -= timedelta(days=1)

            expiry_dt = day.replace(hour=8, minute=0, second=0)
            if start_dt <= expiry_dt <= end_dt:
                expiry_dates.append(expiry_dt)

            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)

        return pd.DatetimeIndex(expiry_dates)

    # ── CONVENIENCE: LOAD ALL DATA FOR A STRATEGY ─────────

    def load_strategy_data(
        self,
        symbol: str,
        timeframe: str,
        start: str,
        end: str,
        include_funding: bool = False,
    ) -> dict:
        """
        Returns dict with 'ohlcv' and optionally 'funding' keys.
        """
        result = {"ohlcv": self.fetch_ohlcv(symbol, timeframe, start, end)}

        if include_funding and "XAU" not in symbol:
            result["funding"] = self.fetch_funding_rates(symbol, start, end)
            result["oi_proxy"] = self.fetch_open_interest_proxy(
                symbol, timeframe, start, end
            )

        return result
