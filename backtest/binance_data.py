"""
Binance Data Fetcher for Historical Klines (Candlestick Data)

Supports both public (no API key) and authenticated requests.
For historical data, API keys are optional but recommended for higher rate limits.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from binance.client import Client
from binance.exceptions import BinanceAPIException
import time


class BinanceDataFetcher:
    """Fetch historical kline data from Binance"""
    
    # Binance interval mapping
    INTERVAL_MAP = {
        '1m': Client.KLINE_INTERVAL_1MINUTE,
        '3m': Client.KLINE_INTERVAL_3MINUTE,
        '5m': Client.KLINE_INTERVAL_5MINUTE,
        '15m': Client.KLINE_INTERVAL_15MINUTE,
        '30m': Client.KLINE_INTERVAL_30MINUTE,
        '1h': Client.KLINE_INTERVAL_1HOUR,
        '2h': Client.KLINE_INTERVAL_2HOUR,
        '4h': Client.KLINE_INTERVAL_4HOUR,
        '6h': Client.KLINE_INTERVAL_6HOUR,
        '8h': Client.KLINE_INTERVAL_8HOUR,
        '12h': Client.KLINE_INTERVAL_12HOUR,
        '1d': Client.KLINE_INTERVAL_1DAY,
        '3d': Client.KLINE_INTERVAL_3DAY,
        '1w': Client.KLINE_INTERVAL_1WEEK,
        '1M': Client.KLINE_INTERVAL_1MONTH,
    }
    
    def __init__(self, api_key=None, api_secret=None):
        """
        Initialize Binance client
        
        Args:
            api_key: Binance API key (optional for historical data)
            api_secret: Binance API secret (optional for historical data)
        """
        if api_key and api_secret:
            print("🔐 Using authenticated Binance API")
            self.client = Client(api_key, api_secret)
        else:
            print("🌐 Using public Binance API (no authentication)")
            self.client = Client()
        
        self.api_key = api_key
        self.api_secret = api_secret
    
    def fetch_klines(self, symbol='BTCUSDT', interval='15m', start_date=None, end_date=None, limit=1000):
        """
        Fetch kline/candlestick data from Binance
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT', 'ETHUSDT')
            interval: Candle interval ('1m', '5m', '15m', '1h', '4h', '1d', etc.)
            start_date: Start date (string 'YYYY-MM-DD' or datetime object)
            end_date: End date (string 'YYYY-MM-DD' or datetime object)
            limit: Max candles per request (default 1000, max 1000)
        
        Returns:
            pandas DataFrame with OHLCV data
        """
        
        if interval not in self.INTERVAL_MAP:
            raise ValueError(f"Invalid interval. Must be one of: {list(self.INTERVAL_MAP.keys())}")
        
        binance_interval = self.INTERVAL_MAP[interval]
        
        # Convert dates to timestamps
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
        
        if end_date is None:
            end_date = datetime.now()
        
        # If no start date, default to reasonable lookback based on interval
        if start_date is None:
            if interval in ['1m', '3m', '5m']:
                start_date = end_date - timedelta(days=7)
            elif interval in ['15m', '30m']:
                start_date = end_date - timedelta(days=30)
            elif interval in ['1h', '2h', '4h']:
                start_date = end_date - timedelta(days=90)
            else:
                start_date = end_date - timedelta(days=365)
        
        print(f"\n{'='*60}")
        print(f"Fetching Binance Data")
        print(f"{'='*60}")
        print(f"Symbol:     {symbol}")
        print(f"Interval:   {interval}")
        print(f"Start Date: {start_date.strftime('%Y-%m-%d')}")
        print(f"End Date:   {end_date.strftime('%Y-%m-%d')}")
        print(f"{'='*60}\n")
        
        all_klines = []
        current_start = start_date
        
        # Fetch data in chunks (Binance limits to 1000 candles per request)
        chunk_count = 0
        
        while current_start < end_date:
            try:
                # Convert to millisecond timestamp
                start_ms = int(current_start.timestamp() * 1000)
                end_ms = int(end_date.timestamp() * 1000)
                
                # Fetch klines
                klines = self.client.get_klines(
                    symbol=symbol,
                    interval=binance_interval,
                    startTime=start_ms,
                    endTime=end_ms,
                    limit=limit
                )
                
                if not klines:
                    break
                
                all_klines.extend(klines)
                chunk_count += 1
                
                # Update start time for next chunk
                last_timestamp = klines[-1][0]
                current_start = datetime.fromtimestamp(last_timestamp / 1000) + timedelta(milliseconds=1)
                
                print(f"  Chunk {chunk_count}: Retrieved {len(klines)} candles", end='\r')
                
                # Rate limiting - be nice to Binance
                time.sleep(0.1)
                
                # If we got less than limit, we've reached the end
                if len(klines) < limit:
                    break
            
            except BinanceAPIException as e:
                print(f"\n⚠️  Binance API Error: {e}")
                if e.code == -1121:  # Invalid symbol
                    print(f"❌ Invalid symbol: {symbol}")
                    print(f"   Try 'BTCUSDT', 'ETHUSDT', etc.")
                raise
            except Exception as e:
                print(f"\n❌ Error fetching data: {e}")
                raise
        
        print(f"\n✓ Retrieved {len(all_klines)} total candles")
        
        # Convert to DataFrame
        df = self._klines_to_dataframe(all_klines)
        
        # Remove duplicates and sort
        df = df[~df.index.duplicated(keep='first')]
        df = df.sort_index()
        
        print(f"✓ Processed into DataFrame")
        print(f"  Date range: {df.index[0]} to {df.index[-1]}")
        print(f"  Total rows: {len(df)}")
        print(f"  Duration: {(df.index[-1] - df.index[0]).days} days\n")
        
        return df
    
    def _klines_to_dataframe(self, klines):
        """
        Convert raw kline data to pandas DataFrame
        
        Binance kline format:
        [
            Open time, Open, High, Low, Close, Volume,
            Close time, Quote asset volume, Number of trades,
            Taker buy base asset volume, Taker buy quote asset volume, Ignore
        ]
        """
        df = pd.DataFrame(klines, columns=[
            'Open_time', 'Open', 'High', 'Low', 'Close', 'Volume',
            'Close_time', 'Quote_volume', 'Trades', 
            'Taker_buy_base', 'Taker_buy_quote', 'Ignore'
        ])
        
        # Convert timestamp to datetime
        df['Open_time'] = pd.to_datetime(df['Open_time'], unit='ms')
        df['Close_time'] = pd.to_datetime(df['Close_time'], unit='ms')
        
        # Set index to open time
        df.set_index('Open_time', inplace=True)
        
        # Convert price and volume columns to float
        for col in ['Open', 'High', 'Low', 'Close', 'Volume', 'Quote_volume', 
                    'Taker_buy_base', 'Taker_buy_quote']:
            df[col] = df[col].astype(float)
        
        # Convert trades to int
        df['Trades'] = df['Trades'].astype(int)
        
        # Keep only OHLCV columns (standard format)
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        
        return df
    
    def fetch_multiple_symbols(self, symbols, interval='15m', start_date=None, end_date=None):
        """
        Fetch data for multiple symbols
        
        Args:
            symbols: List of symbols ['BTCUSDT', 'ETHUSDT', ...]
            interval: Candle interval
            start_date: Start date
            end_date: End date
        
        Returns:
            Dictionary {symbol: DataFrame}
        """
        results = {}
        
        print(f"\n{'='*60}")
        print(f"Fetching data for {len(symbols)} symbols")
        print(f"{'='*60}\n")
        
        for i, symbol in enumerate(symbols, 1):
            print(f"[{i}/{len(symbols)}] {symbol}")
            try:
                df = self.fetch_klines(symbol, interval, start_date, end_date)
                results[symbol] = df
                print(f"✓ {symbol}: {len(df)} candles\n")
            except Exception as e:
                print(f"❌ {symbol}: Failed - {e}\n")
                continue
        
        print(f"{'='*60}")
        print(f"Completed: {len(results)}/{len(symbols)} symbols")
        print(f"{'='*60}\n")
        
        return results
    
    def get_latest_price(self, symbol='BTCUSDT'):
        """Get current price for a symbol"""
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except Exception as e:
            print(f"Error getting price for {symbol}: {e}")
            return None
    
    def get_exchange_info(self, symbol=None):
        """Get exchange trading rules and symbol information"""
        try:
            if symbol:
                return self.client.get_symbol_info(symbol)
            else:
                return self.client.get_exchange_info()
        except Exception as e:
            print(f"Error getting exchange info: {e}")
            return None


# ============================================
# HELPER FUNCTIONS
# ============================================

def calculate_period_dates(period):
    """
    Convert period string to start/end dates
    
    Args:
        period: String like '1y', '6mo', '90d', '5y', etc.
    
    Returns:
        (start_date, end_date) tuple
    """
    end_date = datetime.now()
    
    if period.endswith('y'):
        years = int(period[:-1])
        start_date = end_date - timedelta(days=365 * years)
    elif period.endswith('mo'):
        months = int(period[:-2])
        start_date = end_date - timedelta(days=30 * months)
    elif period.endswith('d'):
        days = int(period[:-1])
        start_date = end_date - timedelta(days=days)
    elif period.endswith('w'):
        weeks = int(period[:-1])
        start_date = end_date - timedelta(weeks=weeks)
    else:
        raise ValueError(f"Invalid period format: {period}. Use format like '1y', '6mo', '90d', etc.")
    
    return start_date, end_date


def fetch_binance_data(symbol='BTCUSDT', interval='15m', period='5y', api_key=None, api_secret=None):
    """
    Convenience function to fetch Binance data
    
    Args:
        symbol: Trading pair (e.g., 'BTCUSDT')
        interval: Candle interval ('15m', '1h', '1d', etc.)
        period: Time period ('5y', '1y', '6mo', '90d', etc.)
        api_key: Binance API key (optional)
        api_secret: Binance API secret (optional)
    
    Returns:
        pandas DataFrame with OHLCV data
    """
    # Calculate dates from period
    start_date, end_date = calculate_period_dates(period)
    
    # Create fetcher
    fetcher = BinanceDataFetcher(api_key=api_key, api_secret=api_secret)
    
    # Fetch data
    df = fetcher.fetch_klines(
        symbol=symbol,
        interval=interval,
        start_date=start_date,
        end_date=end_date
    )
    
    return df


# ============================================
# TESTING
# ============================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("Binance Data Fetcher - Test")
    print("="*60)
    
    # Test 1: Fetch BTC data
    print("\n1. Testing BTC-USDT fetch (last 30 days, 15m interval)")
    df = fetch_binance_data(symbol='BTCUSDT', interval='15m', period='30d')
    print(f"\nFirst few rows:")
    print(df.head())
    print(f"\nLast few rows:")
    print(df.tail())
    print(f"\nDataFrame info:")
    print(df.info())
    
    # Test 2: Fetch multiple symbols
    print("\n\n2. Testing multiple symbols fetch")
    fetcher = BinanceDataFetcher()
    results = fetcher.fetch_multiple_symbols(
        symbols=['BTCUSDT', 'ETHUSDT', 'BNBUSDT'],
        interval='1h',
        period='7d'
    )
    
    for symbol, df in results.items():
        print(f"{symbol}: {len(df)} candles")
    
    # Test 3: Get current price
    print("\n\n3. Testing current price fetch")
    fetcher = BinanceDataFetcher()
    price = fetcher.get_latest_price('BTCUSDT')
    print(f"Current BTC-USDT price: ${price:,.2f}")
    
    print("\n" + "="*60)
    print("All tests completed!")
    print("="*60)
