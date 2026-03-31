"""
VectorBT Backtesting Script for Optimized Trading Strategy
BTC-USD | 15-minute timeframe

NOTE: Yahoo Finance limits 15-minute data to ~60 days max.
For longer periods, this script will use daily data or fetch multiple periods.
"""

import numpy as np
import pandas as pd
import yfinance as yf
import vectorbt as vbt
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Import our optimized strategy
from optimized_strategy import (
    add_all_indicators,
    generate_optimized_signals,
    OptimizedConfig
)


# ============================================
# DATA FETCHING
# ============================================

def fetch_btc_data(interval='15m', period='60d'):
    """
    Fetch BTC-USD data
    
    Note: Yahoo Finance limitations:
    - 15m data: max 60 days
    - 1h data: max 730 days
    - 1d data: unlimited
    """
    print(f"\n{'='*60}")
    print(f"Fetching BTC-USD data...")
    print(f"Interval: {interval} | Period: {period}")
    print(f"{'='*60}\n")
    
    ticker = yf.Ticker("BTC-USD")
    df = ticker.history(interval=interval, period=period)
    
    if df.empty:
        raise ValueError("No data retrieved. Check symbol and period.")
    
    print(f"✓ Retrieved {len(df)} candles")
    print(f"  Date range: {df.index[0]} to {df.index[-1]}")
    print(f"  Duration: {(df.index[-1] - df.index[0]).days} days")
    
    return df


def fetch_multiple_periods(interval='15m', days_back=60):
    """
    Fetch data in chunks if needed (for intervals with limitations)
    This is a workaround for Yahoo Finance limits
    """
    all_data = []
    current_end = datetime.now()
    
    # For 15m data, fetch in 60-day chunks
    chunk_days = 60 if interval == '15m' else 730
    num_chunks = max(1, days_back // chunk_days)
    
    print(f"Fetching {num_chunks} chunks of data...")
    
    for i in range(num_chunks):
        try:
            ticker = yf.Ticker("BTC-USD")
            df_chunk = ticker.history(interval=interval, period=f"{chunk_days}d")
            
            if not df_chunk.empty:
                all_data.append(df_chunk)
                print(f"  Chunk {i+1}/{num_chunks}: {len(df_chunk)} candles")
        except Exception as e:
            print(f"  Error fetching chunk {i+1}: {e}")
    
    if all_data:
        df = pd.concat(all_data).sort_index()
        df = df[~df.index.duplicated(keep='first')]  # Remove duplicates
        return df
    else:
        raise ValueError("Could not fetch any data")


# ============================================
# SIGNAL GENERATION FOR VECTORBT
# ============================================

class StrategySignals:
    """Generate vectorbt-compatible entry/exit signals"""
    
    def __init__(self, df):
        self.df = df.copy()
        self.signals_data = None
        
    def generate(self):
        """Generate all signals for backtesting"""
        print("\n" + "="*60)
        print("Generating trading signals...")
        print("="*60 + "\n")
        
        # Add all indicators
        self.df = add_all_indicators(self.df)
        
        # Initialize signal arrays
        entries = pd.Series(False, index=self.df.index)
        exits = pd.Series(False, index=self.df.index)
        stop_losses = pd.Series(np.nan, index=self.df.index)
        take_profits = pd.Series(np.nan, index=self.df.index)
        
        # Generate signals bar by bar (vectorized where possible)
        print("Processing candles...")
        
        # We need to process iteratively to get proper signals
        # But we'll optimize by doing it in chunks
        window_size = 50  # Lookback window for signal generation
        
        for i in range(window_size, len(self.df)):
            # Get window of data
            df_window = self.df.iloc[:i+1].copy()
            
            try:
                # Generate signals for this point
                result = generate_optimized_signals(df_window)
                signals = result['trade_signals']
                summary = result['summary']
                
                # Check for entry signals
                for signal in signals:
                    if signal['type'] == 'BUY' and signal['strength'] in ['MEDIUM', 'STRONG']:
                        entries.iloc[i] = True
                        
                        # Set stop loss and take profit
                        stop_losses.iloc[i] = summary['stop_loss']
                        take_profits.iloc[i] = summary['take_profit']
                        break
                    
                    elif signal['type'] == 'SELL':
                        # For now, we're only doing long trades
                        # SELL signals will be exit signals
                        exits.iloc[i] = True
                        break
            
            except Exception as e:
                # Skip this bar if error
                continue
            
            # Progress indicator
            if i % 500 == 0:
                progress = (i / len(self.df)) * 100
                print(f"  Progress: {progress:.1f}%", end='\r')
        
        print(f"  Progress: 100.0%")
        
        # Count signals
        num_entries = entries.sum()
        num_exits = exits.sum()
        
        print(f"\n✓ Signal generation complete")
        print(f"  Entry signals: {num_entries}")
        print(f"  Exit signals: {num_exits}")
        
        self.signals_data = {
            'entries': entries,
            'exits': exits,
            'stop_losses': stop_losses,
            'take_profits': take_profits,
        }
        
        return self.signals_data


# ============================================
# VECTORBT BACKTESTING
# ============================================

def run_backtest(df, signals, initial_capital=10000, commission=0.001):
    """
    Run backtest using vectorbt
    
    Args:
        df: OHLCV dataframe
        signals: dict with entries, exits, stop_losses, take_profits
        initial_capital: starting capital
        commission: trading fee (0.001 = 0.1%)
    """
    print("\n" + "="*60)
    print("Running backtest with vectorbt...")
    print("="*60 + "\n")
    
    # Extract signals
    entries = signals['entries']
    exits = signals['exits']
    stop_losses = signals['stop_losses']
    take_profits = signals['take_profits']
    
    # Create portfolio with stop loss and take profit
    print("Building portfolio...")
    
    portfolio = vbt.Portfolio.from_signals(
        close=df['Close'],
        entries=entries,
        exits=exits,
        sl_stop=stop_losses,  # Stop loss prices
        tp_stop=take_profits,  # Take profit prices
        init_cash=initial_capital,
        fees=commission,
        freq='15T'  # 15-minute frequency
    )
    
    print("✓ Backtest complete\n")
    
    return portfolio


# ============================================
# PERFORMANCE ANALYSIS
# ============================================

def analyze_performance(portfolio, df):
    """Generate comprehensive performance metrics"""
    
    print("="*60)
    print("BACKTEST RESULTS")
    print("="*60 + "\n")
    
    # Get statistics
    stats = portfolio.stats()
    
    # Basic metrics
    print("📊 PORTFOLIO METRICS")
    print("-" * 40)
    print(f"Initial Capital:     ${stats['Start Value']:,.2f}")
    print(f"Final Value:         ${stats['End Value']:,.2f}")
    print(f"Total Return:        {stats['Total Return [%]']:.2f}%")
    print(f"Benchmark Return:    {stats['Benchmark Return [%]']:.2f}%")
    print(f"Max Drawdown:        {stats['Max Drawdown [%]']:.2f}%")
    
    # Risk metrics
    print(f"\n📈 RISK METRICS")
    print("-" * 40)
    print(f"Sharpe Ratio:        {stats['Sharpe Ratio']:.2f}")
    print(f"Sortino Ratio:       {stats['Sortino Ratio']:.2f}")
    print(f"Calmar Ratio:        {stats['Calmar Ratio']:.2f}")
    
    # Trade metrics
    print(f"\n💼 TRADE METRICS")
    print("-" * 40)
    print(f"Total Trades:        {stats['Total Trades']}")
    print(f"Win Rate:            {stats['Win Rate [%]']:.2f}%")
    print(f"Best Trade:          {stats['Best Trade [%]']:.2f}%")
    print(f"Worst Trade:         {stats['Worst Trade [%]']:.2f}%")
    print(f"Avg Winning Trade:   {stats['Avg Winning Trade [%]']:.2f}%")
    print(f"Avg Losing Trade:    {stats['Avg Losing Trade [%]']:.2f}%")
    
    # Profit metrics
    print(f"\n💰 PROFIT METRICS")
    print("-" * 40)
    print(f"Profit Factor:       {stats['Profit Factor']:.2f}")
    print(f"Expectancy:          ${stats['Expectancy']:.2f}")
    
    print("\n" + "="*60)
    
    return stats


def plot_results(portfolio, df, save_path='backtest_results.html'):
    """Create interactive visualization"""
    print(f"\n📊 Generating interactive charts...")
    
    # Create figure with portfolio performance
    fig = portfolio.plot()
    
    # Save to HTML
    fig.write_html(save_path)
    print(f"✓ Chart saved to: {save_path}")
    
    return fig


# ============================================
# OPTIMIZATION (OPTIONAL)
# ============================================

def optimize_parameters(df, param_grid):
    """
    Optimize strategy parameters using grid search
    
    Example param_grid:
    {
        'zigzag_threshold': [0.02, 0.03, 0.04, 0.05],
        'min_confluence': [2, 3, 4],
        'stop_loss_mult': [1.0, 1.5, 2.0],
    }
    """
    print("\n" + "="*60)
    print("PARAMETER OPTIMIZATION")
    print("="*60 + "\n")
    
    best_sharpe = -np.inf
    best_params = None
    results = []
    
    # Generate all parameter combinations
    from itertools import product
    
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    
    for combo in product(*values):
        params = dict(zip(keys, combo))
        
        print(f"Testing: {params}")
        
        try:
            # Update config
            if 'zigzag_threshold' in params:
                OptimizedConfig.ZIGZAG_BASE_THRESHOLD = params['zigzag_threshold']
            if 'min_confluence' in params:
                OptimizedConfig.MIN_CONFLUENCE_SCORE = params['min_confluence']
            if 'stop_loss_mult' in params:
                OptimizedConfig.STOP_LOSS_ATR_MULT = params['stop_loss_mult']
            
            # Generate signals
            sig_gen = StrategySignals(df)
            signals = sig_gen.generate()
            
            # Run backtest
            portfolio = run_backtest(df, signals, initial_capital=10000)
            
            # Get Sharpe ratio
            sharpe = portfolio.sharpe_ratio()
            
            results.append({
                'params': params.copy(),
                'sharpe': sharpe,
                'total_return': portfolio.total_return() * 100,
                'max_drawdown': portfolio.max_drawdown() * 100,
            })
            
            print(f"  Sharpe: {sharpe:.2f} | Return: {portfolio.total_return()*100:.2f}%\n")
            
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_params = params.copy()
        
        except Exception as e:
            print(f"  Error: {e}\n")
            continue
    
    print("="*60)
    print("OPTIMIZATION RESULTS")
    print("="*60)
    print(f"\nBest Parameters: {best_params}")
    print(f"Best Sharpe Ratio: {best_sharpe:.2f}")
    
    # Show top 5 results
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values('sharpe', ascending=False)
    print("\nTop 5 Parameter Sets:")
    print(results_df.head().to_string())
    
    return best_params, results_df


# ============================================
# MAIN EXECUTION
# ============================================

def main():
    """Main execution function"""
    
    print("\n" + "="*60)
    print("BTC-USD STRATEGY BACKTEST")
    print("Optimized ZigZag + Confluence Strategy")
    print("="*60)
    
    # Configuration
    INTERVAL = '15m'
    PERIOD = '60d'  # Yahoo Finance limit for 15m data
    INITIAL_CAPITAL = 10000
    COMMISSION = 0.001  # 0.1% per trade
    
    try:
        # Step 1: Fetch data
        df = fetch_btc_data(interval=INTERVAL, period=PERIOD)
        
        # Step 2: Generate signals
        signal_generator = StrategySignals(df)
        signals = signal_generator.generate()
        
        # Step 3: Run backtest
        portfolio = run_backtest(
            df=signal_generator.df,  # Use the df with indicators
            signals=signals,
            initial_capital=INITIAL_CAPITAL,
            commission=COMMISSION
        )
        
        # Step 4: Analyze performance
        stats = analyze_performance(portfolio, df)
        
        # Step 5: Visualize results
        plot_results(portfolio, df, save_path='/home/claude/backtest_results.html')
        
        # Step 6: Save detailed results
        print("\n📝 Saving detailed results...")
        
        # Save trade log
        trades = portfolio.trades.records_readable
        trades.to_csv('/home/claude/trade_log.csv', index=False)
        print(f"✓ Trade log saved: trade_log.csv ({len(trades)} trades)")
        
        # Save portfolio value over time
        portfolio_value = portfolio.value()
        portfolio_value.to_csv('/home/claude/portfolio_value.csv')
        print(f"✓ Portfolio value saved: portfolio_value.csv")
        
        # Save all statistics
        stats_df = pd.DataFrame([stats])
        stats_df.to_csv('/home/claude/statistics.csv', index=False)
        print(f"✓ Statistics saved: statistics.csv")
        
        print("\n✅ Backtest complete!")
        print("\nGenerated files:")
        print("  - backtest_results.html (interactive chart)")
        print("  - trade_log.csv (all trades)")
        print("  - portfolio_value.csv (portfolio over time)")
        print("  - statistics.csv (performance metrics)")
        
        return portfolio, stats
    
    except Exception as e:
        print(f"\n❌ Error during backtest: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def run_optimization():
    """Run parameter optimization"""
    
    # Fetch data
    df = fetch_btc_data(interval='15m', period='60d')
    
    # Define parameter grid
    param_grid = {
        'zigzag_threshold': [0.02, 0.03, 0.04],
        'min_confluence': [2, 3, 4],
        'stop_loss_mult': [1.0, 1.5, 2.0],
    }
    
    # Run optimization
    best_params, results = optimize_parameters(df, param_grid)
    
    # Save results
    results.to_csv('/home/claude/optimization_results.csv', index=False)
    print(f"\n✓ Optimization results saved to: optimization_results.csv")
    
    return best_params, results


if __name__ == "__main__":
    # Run main backtest
    portfolio, stats = main()
    
    # Uncomment to run optimization
    # best_params, opt_results = run_optimization()
