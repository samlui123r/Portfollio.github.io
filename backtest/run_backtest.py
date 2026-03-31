#!/usr/bin/env python3
"""
Quick Start Runner for BTC-USD Strategy Backtest

Usage:
    python run_backtest.py                    # Run standard backtest
    python run_backtest.py --optimize         # Run parameter optimization
    python run_backtest.py --interval 1h      # Use hourly data
    python run_backtest.py --period 2y        # Use 2 years of data
"""

import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description='Run BTC-USD Strategy Backtest')
    
    parser.add_argument('--interval', type=str, default='15m',
                       choices=['1m', '5m', '15m', '30m', '1h', '4h', '1d'],
                       help='Candle interval (default: 15m)')
    
    parser.add_argument('--period', type=str, default='60d',
                       help='Data period (e.g., 60d, 3mo, 1y, 2y) - Note: 15m limited to ~60d')
    
    parser.add_argument('--capital', type=float, default=10000,
                       help='Initial capital (default: 10000)')
    
    parser.add_argument('--commission', type=float, default=0.001,
                       help='Trading fee as decimal (default: 0.001 = 0.1%%)')
    
    parser.add_argument('--optimize', action='store_true',
                       help='Run parameter optimization instead of single backtest')
    
    args = parser.parse_args()
    
    # Import here to show args first
    from vectorbt_backtest import (
        fetch_btc_data,
        StrategySignals,
        run_backtest,
        analyze_performance,
        plot_results,
        run_optimization
    )
    import pandas as pd
    
    print("\n" + "="*60)
    print("BTC-USD Strategy Backtest Runner")
    print("="*60)
    print(f"\nConfiguration:")
    print(f"  Interval:     {args.interval}")
    print(f"  Period:       {args.period}")
    print(f"  Capital:      ${args.capital:,.2f}")
    print(f"  Commission:   {args.commission*100}%")
    print(f"  Mode:         {'OPTIMIZATION' if args.optimize else 'BACKTEST'}")
    print("="*60)
    
    if args.optimize:
        # Run optimization
        print("\nRunning parameter optimization...")
        best_params, results = run_optimization()
        
    else:
        # Run standard backtest
        try:
            # Fetch data
            df = fetch_btc_data(interval=args.interval, period=args.period)
            
            # Generate signals
            signal_generator = StrategySignals(df)
            signals = signal_generator.generate()
            
            # Run backtest
            portfolio = run_backtest(
                df=signal_generator.df,
                signals=signals,
                initial_capital=args.capital,
                commission=args.commission
            )
            
            # Analyze
            stats = analyze_performance(portfolio, df)
            
            # Plot
            plot_results(portfolio, df, save_path='/home/claude/backtest_results.html')
            
            # Save results
            print("\n📝 Saving results...")
            
            trades = portfolio.trades.records_readable
            trades.to_csv('/home/claude/trade_log.csv', index=False)
            
            portfolio_value = portfolio.value()
            portfolio_value.to_csv('/home/claude/portfolio_value.csv')
            
            stats_df = pd.DataFrame([stats])
            stats_df.to_csv('/home/claude/statistics.csv', index=False)
            
            print("\n✅ Backtest complete!")
            print("\nFiles generated:")
            print("  - backtest_results.html")
            print("  - trade_log.csv")
            print("  - portfolio_value.csv")
            print("  - statistics.csv")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    main()
