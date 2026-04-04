"""
=============================================================
 ANALYSIS & REPORTER
 Generates performance tables, equity curves, monthly
 returns heatmap, and trade-level CSV exports.
=============================================================
"""

import pandas as pd
import numpy as np
import vectorbt as vbt
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import seaborn as sns
import os
import logging
from pathlib import Path

from config import RESULTS_DIR, SAVE_PLOTS, SAVE_CSV, LEVERAGE

logger = logging.getLogger(__name__)
Path(RESULTS_DIR).mkdir(exist_ok=True)

# ── Matplotlib style ──────────────────────────────────────
plt.style.use("dark_background")
COLORS = {
    "green"  : "#00ff88",
    "red"    : "#ff4444",
    "blue"   : "#4488ff",
    "yellow" : "#ffcc00",
    "gray"   : "#888888",
    "bg"     : "#0d0d0d",
    "panel"  : "#1a1a1a",
}


# ─── STATS EXTRACTION ─────────────────────────────────────

def extract_stats(
    portfolio: vbt.Portfolio,
    strategy_name: str,
    symbol: str,
    side: str,
    leverage: float = LEVERAGE,
) -> dict:
    """
    Pulls key metrics from vectorbt Portfolio and adds leverage-adjusted returns.
    """
    try:
        s = portfolio.stats()
    except Exception as e:
        logger.error(f"Stats failed: {e}")
        return {}

    total_return    = s.get("Total Return [%]", 0)
    max_dd          = s.get("Max Drawdown [%]", 0)
    win_rate        = s.get("Win Rate [%]", 0)
    n_trades        = s.get("Total Trades", 0)
    sharpe          = s.get("Sharpe Ratio", np.nan)
    sortino         = s.get("Sortino Ratio", np.nan)
    calmar          = s.get("Calmar Ratio", np.nan)

    # Leverage-adjusted estimates (linear approximation)
    lev_total_ret   = total_return * leverage
    lev_max_dd      = min(max_dd * leverage, 100)

    return {
        "Strategy"          : strategy_name,
        "Symbol"            : symbol,
        "Side"              : side,
        "Total Return %"    : round(total_return, 2),
        "Lev Return %"      : round(lev_total_ret, 1),
        "Max Drawdown %"    : round(max_dd, 2),
        "Lev Max DD %"      : round(lev_max_dd, 1),
        "Win Rate %"        : round(win_rate, 1),
        "Sharpe"            : round(sharpe, 3) if not np.isnan(sharpe) else "N/A",
        "Sortino"           : round(sortino, 3) if not np.isnan(sortino) else "N/A",
        "Calmar"            : round(calmar, 3) if not np.isnan(calmar) else "N/A",
        "Total Trades"      : int(n_trades),
        "Trades/Month"      : round(n_trades / max(1, _months_in_portfolio(portfolio)), 1),
    }


def _months_in_portfolio(portfolio: vbt.Portfolio) -> float:
    try:
        wrapper = portfolio.wrapper
        start = wrapper.index[0]
        end   = wrapper.index[-1]
        return max((end - start).days / 30.44, 1)
    except:
        return 12


# ─── MONTHLY RETURNS ──────────────────────────────────────

def monthly_returns_table(portfolio: vbt.Portfolio) -> pd.DataFrame:
    """Returns pivot table of monthly returns (rows=year, cols=month)."""
    try:
        returns = portfolio.returns()
        monthly = (1 + returns).resample("ME").prod() - 1
        monthly.index = monthly.index.to_period("M")
        df = monthly.to_frame("return")
        df["year"]  = df.index.year
        df["month"] = df.index.month
        pivot = df.pivot(index="year", columns="month", values="return") * 100
        pivot.columns = [
            "Jan","Feb","Mar","Apr","May","Jun",
            "Jul","Aug","Sep","Oct","Nov","Dec"
        ][:len(pivot.columns)]
        return pivot
    except Exception as e:
        logger.warning(f"Monthly returns failed: {e}")
        return pd.DataFrame()


# ─── PLOTS ────────────────────────────────────────────────

def plot_equity_curves(
    portfolios: list[tuple],   # list of (portfolio, label, color)
    title: str,
    save_path: str = None,
) -> None:
    """
    Overlaid equity curves for multiple portfolios.
    """
    fig, axes = plt.subplots(2, 1, figsize=(16, 10), facecolor=COLORS["bg"])
    ax1, ax2 = axes

    for pf, label, color in portfolios:
        try:
            value = pf.value()
            value.plot(ax=ax1, label=label, color=color, linewidth=1.5)
            dd = pf.drawdown() * 100
            dd.plot(ax=ax2, label=label, color=color, linewidth=1.0, alpha=0.7)
        except Exception as e:
            logger.warning(f"Plot failed for {label}: {e}")

    ax1.set_title(title, color="white", fontsize=14, pad=10)
    ax1.set_ylabel("Portfolio Value ($)", color="white")
    ax1.legend(facecolor=COLORS["panel"], labelcolor="white", fontsize=9)
    ax1.set_facecolor(COLORS["panel"])
    ax1.tick_params(colors="white")
    ax1.grid(alpha=0.2, color=COLORS["gray"])

    ax2.set_title("Drawdown (%)", color="white", fontsize=12)
    ax2.set_ylabel("Drawdown %", color="white")
    ax2.set_facecolor(COLORS["panel"])
    ax2.tick_params(colors="white")
    ax2.grid(alpha=0.2, color=COLORS["gray"])
    ax2.fill_between(ax2.lines[0].get_xdata(), 0, ax2.lines[0].get_ydata(),
                     alpha=0.2, color=COLORS["red"]) if ax2.lines else None

    plt.tight_layout(pad=2)

    if save_path and SAVE_PLOTS:
        plt.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=COLORS["bg"])
        logger.info(f"[SAVED] {save_path}")
    plt.show()


def plot_monthly_heatmap(
    portfolio: vbt.Portfolio,
    strategy_name: str,
    save_path: str = None,
) -> None:
    """Monthly returns heatmap — key tool for spotting seasonal patterns."""
    monthly = monthly_returns_table(portfolio)
    if monthly.empty:
        return

    fig, ax = plt.subplots(figsize=(14, 5), facecolor=COLORS["bg"])
    sns.heatmap(
        monthly,
        annot=True,
        fmt=".1f",
        center=0,
        cmap="RdYlGn",
        linewidths=0.5,
        linecolor=COLORS["panel"],
        ax=ax,
        cbar_kws={"label": "Return %"},
    )
    ax.set_title(f"{strategy_name} — Monthly Returns (%)", color="white", pad=10)
    ax.set_facecolor(COLORS["panel"])
    plt.tight_layout()

    if save_path and SAVE_PLOTS:
        plt.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=COLORS["bg"])
        logger.info(f"[SAVED] {save_path}")
    plt.show()


def plot_optimization_heatmap(
    opt_results: pd.DataFrame,
    x_param: str,
    y_param: str,
    metric: str = "sharpe",
    strategy_name: str = "",
    save_path: str = None,
) -> None:
    """2D parameter optimization heatmap (Sharpe or return)."""
    if opt_results.empty or len(opt_results) < 4:
        logger.warning("Insufficient optimization results for heatmap")
        return

    try:
        pivot = opt_results.pivot_table(
            index=y_param, columns=x_param, values=metric, aggfunc="mean"
        )
        fig, ax = plt.subplots(figsize=(12, 7), facecolor=COLORS["bg"])
        sns.heatmap(
            pivot, annot=True, fmt=".2f", cmap="viridis",
            linewidths=0.3, ax=ax,
        )
        ax.set_title(
            f"{strategy_name} Optimization: {metric.title()} ({x_param} vs {y_param})",
            color="white", pad=10
        )
        ax.set_facecolor(COLORS["panel"])
        plt.tight_layout()

        if save_path and SAVE_PLOTS:
            plt.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=COLORS["bg"])
        plt.show()
    except Exception as e:
        logger.warning(f"Optimization heatmap failed: {e}")


# ─── SUMMARY TABLE ────────────────────────────────────────

def print_summary_table(all_stats: list[dict]) -> pd.DataFrame:
    """
    Pretty prints summary of all strategies.
    Returns DataFrame for CSV export.
    """
    if not all_stats:
        print("No results to display.")
        return pd.DataFrame()

    df = pd.DataFrame(all_stats)
    df = df.sort_values("Sharpe", ascending=False)

    print("\n" + "═" * 100)
    print(" BACKTEST RESULTS SUMMARY ".center(100, "═"))
    print("═" * 100)
    print(df.to_string(index=False))
    print("═" * 100)

    # Best configuration per strategy
    print("\n TOP CONFIGURATION PER STRATEGY ".center(100, "─"))
    for strategy in df["Strategy"].unique():
        best = df[df["Strategy"] == strategy].iloc[0]
        print(f"\n  {best['Strategy']} ({best['Symbol']} {best['Side']})")
        print(f"  Return: {best['Total Return %']}% | Leveraged: {best['Lev Return %']}%")
        print(f"  Sharpe: {best['Sharpe']} | Win Rate: {best['Win Rate %']}% | "
              f"Trades: {best['Total Trades']} | DD: {best['Max Drawdown %']}%")

    return df


# ─── EXPORT ───────────────────────────────────────────────

def export_trades(portfolio: vbt.Portfolio, filename: str) -> None:
    """Export individual trade log to CSV."""
    if not SAVE_CSV:
        return
    try:
        trades = portfolio.trades.records_readable
        path = os.path.join(RESULTS_DIR, filename)
        trades.to_csv(path, index=False)
        logger.info(f"[EXPORTED] Trades → {path}")
    except Exception as e:
        logger.warning(f"Trade export failed: {e}")


def export_summary(df: pd.DataFrame, filename: str = "summary.csv") -> None:
    """Export summary stats table to CSV."""
    if not SAVE_CSV:
        return
    path = os.path.join(RESULTS_DIR, filename)
    df.to_csv(path, index=False)
    logger.info(f"[EXPORTED] Summary → {path}")


def export_optimization(opt_df: pd.DataFrame, strategy_name: str) -> None:
    """Export optimization results to CSV."""
    if not SAVE_CSV or opt_df.empty:
        return
    filename = f"opt_{strategy_name.lower().replace(' ', '_')}.csv"
    path = os.path.join(RESULTS_DIR, filename)
    opt_df.to_csv(path, index=False)
    logger.info(f"[EXPORTED] Optimization → {path}")
