#!/usr/bin/env python3
"""
Quick Start Runner for Binance Strategy Backtest

Now with full 5-year data support using Binance API!

Usage:
    python run_binance_backtest.py                           # Use defaults from config
    python run_binance_backtest.py --symbol ETHUSDT          # Test ETH
    python run_binance_backtest.py --interval 1h --period 2y # 2 years hourly
    python run_binance_backtest.py --optimize                # Find best parameters
"""

import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description='Run Binance Strategy Backtest')
    
    parser.add_argument('--symbol', type=str, default='BTCUSDT',
                       help='Trading pair (default: BTCUSDT). Examples: ETHUSDT, BNBUSDT, SOLUSDT')
    
    parser.add_argument('--interval', type=str, default='15m',
                       choices=['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w'],
                       help='Candle interval (default: 15m)')
    
    parser.add_argument('--period', type=str, default='5y',
                       help='Data period (e.g., 5y, 2y, 1y, 6mo, 90d, 30d)')
    
    parser.add_argument('--capital', type=float, default=10000,
                       help='Initial capital (default: 10000)')
    
    parser.add_argument('--commission', type=float, default=0.001,
                       help='Trading fee as decimal (default: 0.001 = 0.1%% - typical Binance fee)')
    
    parser.add_argument('--optimize', action='store_true',
                       help='Run parameter optimization instead of single backtest')
    
    parser.add_argument('--api-key', type=str, default=None,
                       help='Binance API key (optional - uses public API if not provided)')
    
    parser.add_argument('--api-secret', type=str, default=None,
                       help='Binance API secret (optional)')
    
    args = parser.parse_args()
    
    # Import here to show args first
    from vectorbt_backtest_binance import (
        main as run_backtest,
        run_optimization
    )
    from config_binance import get_api_credentials
    import pandas as pd
    
    print("\n" + "="*60)
    print("BINANCE Strategy Backtest Runner")
    print("="*60)
    print(f"\nConfiguration:")
    print(f"  Symbol:       {args.symbol}")
    print(f"  Interval:     {args.interval}")
    print(f"  Period:       {args.period}")
    print(f"  Capital:      ${args.capital:,.2f}")
    print(f"  Commission:   {args.commission*100}%")
    
    # Handle API credentials
    if args.api_key and args.api_secret:
        api_key = args.api_key
        api_secret = args.api_secret
        print(f"  API Auth:     Command-line provided")
    else:
        api_key, api_secret = get_api_credentials()
        if api_key:
            print(f"  API Auth:     Config file (api_key: {api_key[:8]}...)")
        else:
            print(f"  API Auth:     Public API (no authentication)")
    
    print(f"  Mode:         {'OPTIMIZATION' if args.optimize else 'BACKTEST'}")
    print("="*60)
    
    if args.optimize:
        # Run optimization
        print("\nRunning parameter optimization...")
        try:
            best_params, results = run_optimization(
                symbol=args.symbol,
                interval=args.interval,
                period=args.period
            )
            print("\n✅ Optimization complete!")
            print(f"\nBest parameters: {best_params}")
            
        except Exception as e:
            print(f"\n❌ Error during optimization: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    else:
        # Run standard backtest
        try:
            portfolio, stats = run_backtest(
                symbol=args.symbol,
                interval=args.interval,
                period=args.period,
                api_key=api_key,
                api_secret=api_secret
            )
            
            if portfolio is None:
                print("\n❌ Backtest failed!")
                sys.exit(1)
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    main()
