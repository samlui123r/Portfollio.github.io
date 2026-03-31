"""
Binance API Configuration

IMPORTANT: 
- For historical data (klines), API keys are OPTIONAL - the data is public
- API keys provide higher rate limits and access to account-specific endpoints
- Never commit this file with real credentials to version control

To use API keys:
1. Go to https://www.binance.com/en/my/settings/api-management
2. Create a new API key
3. Enable "Enable Reading" permission (no trading permissions needed)
4. Copy your API key and secret below
5. Keep this file secure!
"""

# ============================================
# BINANCE API CREDENTIALS
# ============================================

# Option 1: Enter your credentials directly here
BINANCE_API_KEY = ""  # Your Binance API key
BINANCE_API_SECRET = ""  # Your Binance API secret

# Option 2: Leave empty to use public API (no authentication)
# Public API works fine for historical data but has lower rate limits

# ============================================
# BINANCE CONFIGURATION
# ============================================

# Default symbol to trade
DEFAULT_SYMBOL = "BTCUSDT"  # BTC/USDT pair

# Use Binance.US instead of Binance.com?
USE_BINANCE_US = False  # Set to True if you're using Binance.US

# Testnet (for testing without real data)
USE_TESTNET = False  # Set to True to use Binance testnet

# ============================================
# RATE LIMITING
# ============================================

# Delay between requests (seconds)
REQUEST_DELAY = 0.1  # 100ms delay between requests

# Max retries on error
MAX_RETRIES = 3

# ============================================
# DATA PREFERENCES
# ============================================

# Default interval for backtesting
DEFAULT_INTERVAL = "15m"  # 15-minute candles

# Default lookback period
DEFAULT_PERIOD = "5y"  # 5 years of data

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_api_credentials():
    """
    Get API credentials from config
    Returns (api_key, api_secret) tuple or (None, None) if not configured
    """
    if BINANCE_API_KEY and BINANCE_API_SECRET:
        return BINANCE_API_KEY, BINANCE_API_SECRET
    return None, None


def has_api_credentials():
    """Check if API credentials are configured"""
    return bool(BINANCE_API_KEY and BINANCE_API_SECRET)


def validate_credentials():
    """Validate that credentials are properly formatted"""
    if not has_api_credentials():
        return True  # Public API is valid
    
    if not BINANCE_API_KEY or len(BINANCE_API_KEY) < 10:
        return False
    
    if not BINANCE_API_SECRET or len(BINANCE_API_SECRET) < 10:
        return False
    
    return True


# ============================================
# EXAMPLE USAGE
# ============================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("Binance Configuration Check")
    print("="*60 + "\n")
    
    if has_api_credentials():
        print("✓ API credentials found")
        print(f"  API Key: {BINANCE_API_KEY[:8]}...{BINANCE_API_KEY[-4:]}")
        print(f"  Secret:  {BINANCE_API_SECRET[:8]}...{BINANCE_API_SECRET[-4:]}")
        
        if validate_credentials():
            print("✓ Credentials appear valid")
        else:
            print("⚠️  Credentials may be invalid (too short)")
    else:
        print("ℹ️  No API credentials configured")
        print("   Using public API (works fine for historical data)")
    
    print(f"\nDefault Settings:")
    print(f"  Symbol:   {DEFAULT_SYMBOL}")
    print(f"  Interval: {DEFAULT_INTERVAL}")
    print(f"  Period:   {DEFAULT_PERIOD}")
    print(f"  Use US:   {USE_BINANCE_US}")
    print(f"  Testnet:  {USE_TESTNET}")
    
    print("\n" + "="*60)
