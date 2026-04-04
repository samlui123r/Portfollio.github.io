"""
=============================================================
 MAIN BACKTEST ORCHESTRATOR
 Runs all 5 strategies sequentially.
 Outputs: console summary, equity curves, monthly heatmaps,
          optimization tables, trade-level CSVs.

 Usage:
   python main.py                        # Run all strategies
   python main.py --strategy liquidity   # Single strategy
   python main.py --optimize             # Enable optimization
   python main.py --no-plots             # Skip plot rendering
=============================================================
"""

import argparse
import logging
import os
import sys
import warnings
from pathlib import Path

import pandas as pd
import numpy as np

# ── Suppress noisy warnings ───────────────────────────────
warnings.filterwarnings("ignore")

# ── Logging setup ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("backtest.log"),
    ],
)
logger = logging.getLogger("main")

# ── Local imports ─────────────────────────────────────────
from config import (
    BACKTEST_START, BACKTEST_END, INITIAL_CAPITAL, LEVERAGE,
    ASSETS, TIMEFRAMES, RESULTS_DIR,
)
from data.fetcher import BinanceDataFetcher
from strategies import (
    liquidity_sweep,
    volatility_coil,
    funding_exhaustion,
    nfp_compression,
    gamma_squeeze,
)
from analysis.reporter import (
    extract_stats, print_summary_table, plot_equity_curves,
    plot_monthly_heatmap, plot_optimization_heatmap,
    export_trades, export_summary, export_optimization,
    COLORS,
)

Path(RESULTS_DIR).mkdir(exist_ok=True)


# ════════════════════════════════════════════════════════════
#  STRATEGY RUNNERS
# ════════════════════════════════════════════════════════════

def run_liquidity_sweep(fetcher, optimize=False) -> list[dict]:
    logger.info("=" * 60)
    logger.info("STRATEGY 1: LIQUIDITY SWEEP REVERSAL")
    logger.info("=" * 60)

    all_stats  = []
    all_pfs    = []
    opt_frames = []

    for symbol in ASSETS["liquidity_sweep"]:
        tf = TIMEFRAMES["liquidity_sweep"]
        logger.info(f"Loading {symbol} {tf}...")

        try:
            data = fetcher.fetch_ohlcv(symbol, tf, BACKTEST_START, BACKTEST_END)
        except Exception as e:
            logger.error(f"Data fetch failed for {symbol}: {e}")
            continue

        # ── Default backtest ──────────────────────────────
        try:
            pf_long, pf_short = liquidity_sweep.run_backtest(data, symbol, direction="both")

            for pf, side in [(pf_long, "long"), (pf_short, "short")]:
                stats = extract_stats(pf, "Liquidity Sweep", symbol, side)
                if stats:
                    all_stats.append(stats)
                    all_pfs.append((pf, f"{symbol} {side}", COLORS["green"] if side == "long" else COLORS["red"]))
                    export_trades(pf, f"liquidity_sweep_{symbol}_{side}_trades.csv")

        except Exception as e:
            logger.error(f"Backtest failed {symbol}: {e}")
            continue

        # ── Optimization ──────────────────────────────────
        if optimize:
            logger.info(f"Optimizing Liquidity Sweep on {symbol}...")
            opt_df = liquidity_sweep.optimize(data, symbol)
            opt_frames.append(opt_df)
            export_optimization(opt_df, f"liquidity_sweep_{symbol}")
            if not opt_df.empty:
                plot_optimization_heatmap(
                    opt_df[opt_df["side"] == "long"],
                    x_param="sweep_threshold",
                    y_param="rsi_threshold",
                    strategy_name=f"Liquidity Sweep {symbol}",
                    save_path=f"{RESULTS_DIR}/opt_liq_sweep_{symbol}.png",
                )

    # ── Equity curve plot ─────────────────────────────────
    if all_pfs:
        plot_equity_curves(
            all_pfs[:6],  # limit for readability
            title="Strategy 1: Liquidity Sweep Reversal — All Symbols",
            save_path=f"{RESULTS_DIR}/equity_liquidity_sweep.png",
        )
    if all_pfs:
        # Monthly heatmap for first portfolio
        plot_monthly_heatmap(
            all_pfs[0][0],
            "Liquidity Sweep (BTC Long)",
            save_path=f"{RESULTS_DIR}/heatmap_liquidity_sweep.png",
        )

    return all_stats


def run_volatility_coil(fetcher, optimize=False) -> list[dict]:
    logger.info("=" * 60)
    logger.info("STRATEGY 2: VOLATILITY COIL BREAKOUT")
    logger.info("=" * 60)

    all_stats = []
    all_pfs   = []

    for symbol in ASSETS["volatility_coil"]:
        tf = TIMEFRAMES["volatility_coil"]
        logger.info(f"Loading {symbol} {tf}...")

        try:
            data = fetcher.fetch_ohlcv(symbol, tf, BACKTEST_START, BACKTEST_END)
        except Exception as e:
            logger.error(f"Data fetch failed for {symbol}: {e}")
            continue

        try:
            pf_long, pf_short = volatility_coil.run_backtest(data, symbol)

            for pf, side in [(pf_long, "long"), (pf_short, "short")]:
                stats = extract_stats(pf, "Volatility Coil", symbol, side)
                if stats:
                    all_stats.append(stats)
                    all_pfs.append((pf, f"{symbol} {side}", COLORS["blue"] if side == "long" else COLORS["yellow"]))
                    export_trades(pf, f"volatility_coil_{symbol}_{side}_trades.csv")

        except Exception as e:
            logger.error(f"Backtest failed {symbol}: {e}")
            continue

        if optimize:
            logger.info(f"Optimizing Volatility Coil on {symbol}...")
            opt_df = volatility_coil.optimize(data, symbol)
            export_optimization(opt_df, f"volatility_coil_{symbol}")
            if not opt_df.empty:
                plot_optimization_heatmap(
                    opt_df[opt_df["side"] == "long"],
                    x_param="atr_ratio",
                    y_param="tp_mult",
                    strategy_name=f"Volatility Coil {symbol}",
                    save_path=f"{RESULTS_DIR}/opt_vol_coil_{symbol}.png",
                )

    if all_pfs:
        plot_equity_curves(
            all_pfs,
            title="Strategy 2: Volatility Coil Breakout — All Symbols",
            save_path=f"{RESULTS_DIR}/equity_volatility_coil.png",
        )

    return all_stats


def run_funding_exhaustion(fetcher, optimize=False) -> list[dict]:
    logger.info("=" * 60)
    logger.info("STRATEGY 3: FUNDING RATE EXHAUSTION")
    logger.info("=" * 60)

    all_stats = []
    all_pfs   = []

    for symbol in ASSETS["funding_exhaustion"]:
        tf = TIMEFRAMES["funding_exhaustion"]
        logger.info(f"Loading {symbol} {tf} + funding rates...")

        try:
            data = fetcher.fetch_ohlcv(symbol, tf, BACKTEST_START, BACKTEST_END)
            funding  = fetcher.fetch_funding_rates(symbol, BACKTEST_START, BACKTEST_END)
            oi_proxy = fetcher.fetch_open_interest_proxy(symbol, tf, BACKTEST_START, BACKTEST_END)
        except Exception as e:
            logger.error(f"Data fetch failed for {symbol}: {e}")
            continue

        try:
            pf_long, pf_short = funding_exhaustion.run_backtest(
                data, funding, oi_proxy, symbol
            )

            for pf, side in [(pf_long, "long"), (pf_short, "short")]:
                stats = extract_stats(pf, "Funding Exhaustion", symbol, side)
                if stats:
                    all_stats.append(stats)
                    all_pfs.append((pf, f"{symbol} {side}", COLORS["green"] if side == "long" else COLORS["red"]))
                    export_trades(pf, f"funding_exhaustion_{symbol}_{side}_trades.csv")

        except Exception as e:
            logger.error(f"Backtest failed {symbol}: {e}")
            continue

        if optimize:
            logger.info(f"Optimizing Funding Exhaustion on {symbol}...")
            opt_df = funding_exhaustion.optimize(data, funding, oi_proxy, symbol)
            export_optimization(opt_df, f"funding_exhaustion_{symbol}")

    if all_pfs:
        plot_equity_curves(
            all_pfs,
            title="Strategy 3: Funding Rate Exhaustion — All Symbols",
            save_path=f"{RESULTS_DIR}/equity_funding_exhaustion.png",
        )
        plot_monthly_heatmap(
            all_pfs[0][0],
            "Funding Exhaustion (BTC Short)",
            save_path=f"{RESULTS_DIR}/heatmap_funding_exhaustion.png",
        )

    return all_stats


def run_nfp_compression(fetcher, optimize=False) -> list[dict]:
    logger.info("=" * 60)
    logger.info("STRATEGY 4: PRE-NFP COMPRESSION (XAUUSD)")
    logger.info("=" * 60)

    all_stats = []

    symbol = "XAUUSDT"
    tf     = TIMEFRAMES["nfp_compression"]

    try:
        data = fetcher.fetch_ohlcv(symbol, tf, BACKTEST_START, BACKTEST_END)
    except Exception as e:
        logger.error(f"Data fetch failed for {symbol}: {e}")
        return []

    # Get NFP dates for backtest period
    nfp_dates = fetcher.get_nfp_dates(BACKTEST_START, BACKTEST_END)
    logger.info(f"NFP dates found: {len(nfp_dates)}")

    try:
        pf_long, pf_short, setups = nfp_compression.run_backtest(data, nfp_dates, symbol)

        # Log setup statistics
        valid = setups[setups["valid_setup"]]
        logger.info(f"Valid NFP setups: {len(valid)} / {len(setups)} total")
        logger.info(f"Long setups: {(valid['direction'] == 'long').sum()}, "
                    f"Short setups: {(valid['direction'] == 'short').sum()}")

        for pf, side in [(pf_long, "long"), (pf_short, "short")]:
            stats = extract_stats(pf, "Pre-NFP Compression", symbol, side, leverage=30)
            if stats:
                all_stats.append(stats)
                export_trades(pf, f"nfp_compression_{side}_trades.csv")

        # Equity curve for combined view
        plot_equity_curves(
            [(pf_long, "XAUUSD Long", COLORS["green"]),
             (pf_short, "XAUUSD Short", COLORS["red"])],
            title="Strategy 4: Pre-NFP Compression — XAUUSD",
            save_path=f"{RESULTS_DIR}/equity_nfp_compression.png",
        )

    except Exception as e:
        logger.error(f"NFP backtest failed: {e}")

    if optimize:
        logger.info("Optimizing Pre-NFP Compression...")
        opt_df = nfp_compression.optimize(data, nfp_dates, symbol)
        export_optimization(opt_df, "nfp_compression")
        if not opt_df.empty:
            plot_optimization_heatmap(
                opt_df,
                x_param="compress_pct",
                y_param="tp_mult",
                strategy_name="Pre-NFP Compression",
                save_path=f"{RESULTS_DIR}/opt_nfp_compression.png",
            )

    return all_stats


def run_gamma_squeeze(fetcher, optimize=False) -> list[dict]:
    logger.info("=" * 60)
    logger.info("STRATEGY 5: GAMMA SQUEEZE ANTICIPATION (BTC)")
    logger.info("=" * 60)

    all_stats = []

    symbol = "BTCUSDT"
    tf     = TIMEFRAMES["gamma_squeeze"]

    try:
        data = fetcher.fetch_ohlcv(symbol, tf, BACKTEST_START, BACKTEST_END)
    except Exception as e:
        logger.error(f"Data fetch failed for {symbol}: {e}")
        return []

    expiry_dates = fetcher.get_monthly_expiry_dates(BACKTEST_START, BACKTEST_END)
    logger.info(f"Monthly expiry dates: {len(expiry_dates)}")

    try:
        pf_long, pf_short, sigs = gamma_squeeze.run_backtest(data, expiry_dates, symbol)

        for pf, side in [(pf_long, "long"), (pf_short, "short")]:
            stats = extract_stats(pf, "Gamma Squeeze", symbol, side)
            if stats:
                all_stats.append(stats)
                export_trades(pf, f"gamma_squeeze_{side}_trades.csv")

        plot_equity_curves(
            [(pf_long,  "BTC Long (toward proxy)",  COLORS["blue"]),
             (pf_short, "BTC Short (toward proxy)", COLORS["yellow"])],
            title="Strategy 5: Gamma Squeeze Proxy — BTCUSDT",
            save_path=f"{RESULTS_DIR}/equity_gamma_squeeze.png",
        )

    except Exception as e:
        logger.error(f"Gamma squeeze backtest failed: {e}")

    if optimize:
        logger.info("Optimizing Gamma Squeeze...")
        opt_df = gamma_squeeze.optimize(data, expiry_dates, symbol)
        export_optimization(opt_df, "gamma_squeeze")

    return all_stats


# ════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Gold & Crypto Backtest Engine")
    parser.add_argument(
        "--strategy", type=str, default="all",
        choices=["all", "liquidity", "coil", "funding", "nfp", "gamma"],
        help="Which strategy to run",
    )
    parser.add_argument("--optimize", action="store_true", help="Run parameter optimization")
    parser.add_argument("--no-plots",  action="store_true", help="Disable plot rendering")
    parser.add_argument("--no-cache",  action="store_true", help="Force re-download data")
    args = parser.parse_args()

    if args.no_plots:
        import matplotlib
        matplotlib.use("Agg")

    logger.info("▶ BACKTEST ENGINE STARTING")
    logger.info(f"  Period  : {BACKTEST_START} → {BACKTEST_END}")
    logger.info(f"  Capital : ${INITIAL_CAPITAL:,.0f}")
    logger.info(f"  Leverage: {LEVERAGE}x")
    logger.info(f"  Strategy: {args.strategy}")
    logger.info(f"  Optimize: {args.optimize}")

    fetcher   = BinanceDataFetcher()
    all_stats = []

    strategy_map = {
        "liquidity" : run_liquidity_sweep,
        "coil"      : run_volatility_coil,
        "funding"   : run_funding_exhaustion,
        "nfp"       : run_nfp_compression,
        "gamma"     : run_gamma_squeeze,
    }

    if args.strategy == "all":
        targets = list(strategy_map.keys())
    else:
        targets = [args.strategy]

    for name in targets:
        try:
            stats = strategy_map[name](fetcher, optimize=args.optimize)
            all_stats.extend(stats)
        except Exception as e:
            logger.error(f"Strategy {name} failed: {e}", exc_info=True)

    # ── Final summary ─────────────────────────────────────
    if all_stats:
        summary_df = print_summary_table(all_stats)
        export_summary(summary_df, "backtest_summary.csv")
        logger.info(f"\n✅ Results saved to ./{RESULTS_DIR}/")
    else:
        logger.warning("No results generated — check data fetching and error logs.")


if __name__ == "__main__":
    main()
