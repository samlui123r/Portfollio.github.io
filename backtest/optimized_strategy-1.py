"""
Optimized Trading Strategy - Enhanced Signal Generation
Improvements over original:
1. Dynamic parameter adjustment based on volatility
2. Multi-timeframe confluence
3. Enhanced risk management
4. Better signal filtering
"""

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema
import ta

# ============================================
# OPTIMIZED PARAMETERS
# ============================================

class OptimizedConfig:
    """Dynamic configuration that adapts to market conditions"""
    
    # ZigZag - now volatility-adaptive
    ZIGZAG_BASE_THRESHOLD = 0.03  # 3% base (reduced from 5% for more signals)
    ZIGZAG_ORDER = 8  # Reduced for more responsive pivots
    
    # Moving Averages - multiple timeframes
    FAST_MA = 10
    MEDIUM_MA = 20
    SLOW_MA = 50
    TREND_MA = 200
    
    # RSI - dual threshold
    RSI_PERIOD = 14
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    RSI_NEUTRAL_LOW = 45
    RSI_NEUTRAL_HIGH = 55
    
    # MACD
    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9
    
    # Bollinger Bands
    BB_PERIOD = 20
    BB_STD = 2
    
    # ATR for volatility
    ATR_PERIOD = 14
    
    # Risk Management
    STOP_LOSS_ATR_MULT = 1.5  # Tighter stop (was 2)
    TAKE_PROFIT_ATR_MULT = 3.0
    TRAILING_STOP_ATR_MULT = 2.5
    
    # Signal strength thresholds
    MIN_CONFLUENCE_SCORE = 2  # Minimum signals needed
    STRONG_CONFLUENCE_SCORE = 4


# ============================================
# CUSTOM ZIGZAG (Same as original)
# ============================================

def find_zigzag_pivots(prices, threshold=0.03, order=8):
    """Enhanced zigzag with dynamic threshold"""
    prices = np.array(prices, dtype=float)
    n = len(prices)
    
    if n < order * 2:
        raise ValueError(f"Need at least {order * 2} data points, got {n}")
    
    # Find local extrema
    local_max_indices = argrelextrema(prices, np.greater_equal, order=order)[0]
    local_min_indices = argrelextrema(prices, np.less_equal, order=order)[0]
    
    # Combine pivots
    all_pivots = []
    for idx in local_max_indices:
        all_pivots.append({"index": idx, "price": prices[idx], "type": "peak"})
    for idx in local_min_indices:
        all_pivots.append({"index": idx, "price": prices[idx], "type": "valley"})
    
    all_pivots.sort(key=lambda x: x["index"])
    
    # Remove duplicates
    seen = {}
    for p in all_pivots:
        idx = p["index"]
        if idx not in seen:
            seen[idx] = p
        else:
            existing = seen[idx]
            if p["type"] == "peak" and p["price"] > existing["price"]:
                seen[idx] = p
            elif p["type"] == "valley" and p["price"] < existing["price"]:
                seen[idx] = p
    
    all_pivots = list(seen.values())
    all_pivots.sort(key=lambda x: x["index"])
    
    # Filter: alternating and threshold
    filtered = _alternate_pivots(all_pivots)
    filtered = _filter_by_threshold(filtered, threshold)
    
    # Build results
    pivot_indices = [p["index"] for p in filtered]
    pivot_prices = [p["price"] for p in filtered]
    pivot_types = [p["type"] for p in filtered]
    
    pivot_labels = np.zeros(n)
    for p in filtered:
        pivot_labels[p["index"]] = 1 if p["type"] == "peak" else -1
    
    return {
        "pivot_indices": np.array(pivot_indices),
        "pivot_prices": np.array(pivot_prices),
        "pivot_types": pivot_types,
        "pivot_labels": pivot_labels,
        "zigzag_line": _build_zigzag_line(prices, filtered),
        "pivots": filtered,
    }


def _alternate_pivots(pivots):
    """Ensure alternating peaks/valleys"""
    if len(pivots) <= 1:
        return pivots
    
    result = [pivots[0]]
    for i in range(1, len(pivots)):
        current = pivots[i]
        last = result[-1]
        
        if current["type"] == last["type"]:
            if current["type"] == "peak":
                if current["price"] > last["price"]:
                    result[-1] = current
            else:
                if current["price"] < last["price"]:
                    result[-1] = current
        else:
            result.append(current)
    
    return result


def _filter_by_threshold(pivots, threshold):
    """Filter pivots by minimum price change"""
    if len(pivots) <= 2:
        return pivots
    
    filtered = [pivots[0]]
    for i in range(1, len(pivots)):
        last_price = filtered[-1]["price"]
        current_price = pivots[i]["price"]
        pct_change = abs(current_price - last_price) / last_price
        
        if pct_change >= threshold:
            filtered.append(pivots[i])
    
    return filtered


def _build_zigzag_line(prices, pivots):
    """Build continuous zigzag line"""
    n = len(prices)
    zigzag = np.full(n, np.nan)
    
    if len(pivots) == 0:
        return zigzag
    
    for p in pivots:
        zigzag[p["index"]] = p["price"]
    
    for i in range(len(pivots) - 1):
        start_idx = pivots[i]["index"]
        end_idx = pivots[i + 1]["index"]
        start_price = pivots[i]["price"]
        end_price = pivots[i + 1]["price"]
        
        if end_idx > start_idx:
            slope = (end_price - start_price) / (end_idx - start_idx)
            for j in range(start_idx, end_idx + 1):
                zigzag[j] = start_price + slope * (j - start_idx)
    
    return zigzag


# ============================================
# ENHANCED TECHNICAL INDICATORS
# ============================================

def add_all_indicators(df):
    """Add all technical indicators with enhancements"""
    
    # Price columns
    close = df['Close']
    high = df['High']
    low = df['Low']
    volume = df['Volume']
    
    # Multiple Moving Averages
    df['MA_Fast'] = ta.trend.sma_indicator(close, window=OptimizedConfig.FAST_MA)
    df['MA_Medium'] = ta.trend.sma_indicator(close, window=OptimizedConfig.MEDIUM_MA)
    df['MA_Slow'] = ta.trend.sma_indicator(close, window=OptimizedConfig.SLOW_MA)
    df['MA_Trend'] = ta.trend.sma_indicator(close, window=OptimizedConfig.TREND_MA)
    
    # EMA for faster response
    df['EMA_Fast'] = ta.trend.ema_indicator(close, window=OptimizedConfig.FAST_MA)
    df['EMA_Medium'] = ta.trend.ema_indicator(close, window=OptimizedConfig.MEDIUM_MA)
    
    # RSI
    df['RSI'] = ta.momentum.rsi(close, window=OptimizedConfig.RSI_PERIOD)
    
    # MACD
    macd = ta.trend.MACD(close, 
                         window_fast=OptimizedConfig.MACD_FAST,
                         window_slow=OptimizedConfig.MACD_SLOW,
                         window_sign=OptimizedConfig.MACD_SIGNAL)
    df['MACD'] = macd.macd()
    df['MACD_Signal'] = macd.macd_signal()
    df['MACD_Hist'] = macd.macd_diff()
    
    # Bollinger Bands
    bb = ta.volatility.BollingerBands(close, 
                                       window=OptimizedConfig.BB_PERIOD,
                                       window_dev=OptimizedConfig.BB_STD)
    df['BB_Upper'] = bb.bollinger_hband()
    df['BB_Middle'] = bb.bollinger_mavg()
    df['BB_Lower'] = bb.bollinger_lband()
    df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_Middle']
    
    # ATR for volatility
    df['ATR'] = ta.volatility.average_true_range(high, low, close, 
                                                   window=OptimizedConfig.ATR_PERIOD)
    df['ATR_Pct'] = (df['ATR'] / close) * 100
    
    # Volume indicators
    df['Volume_MA'] = volume.rolling(window=20).mean()
    df['Volume_Ratio'] = volume / df['Volume_MA']
    
    # Stochastic for additional momentum
    stoch = ta.momentum.StochasticOscillator(high, low, close, window=14, smooth_window=3)
    df['Stoch_K'] = stoch.stoch()
    df['Stoch_D'] = stoch.stoch_signal()
    
    # ADX for trend strength
    adx = ta.trend.ADXIndicator(high, low, close, window=14)
    df['ADX'] = adx.adx()
    
    return df


# ============================================
# ENHANCED SIGNAL GENERATION
# ============================================

def generate_optimized_signals(df):
    """
    Generate trading signals with confluence detection
    Returns signals with strength scores
    """
    
    # Calculate zigzag
    prices = df['Close'].values
    
    # Dynamic threshold based on recent volatility
    recent_volatility = df['ATR_Pct'].tail(50).mean()
    threshold = max(0.02, min(0.05, recent_volatility / 100))  # 2-5%
    
    zigzag = find_zigzag_pivots(prices, threshold=threshold, order=OptimizedConfig.ZIGZAG_ORDER)
    
    # Get support/resistance
    sr_levels = find_support_resistance(prices, zigzag)
    
    # Analyze trend
    trend = analyze_trend(df)
    
    # Analyze volatility
    volatility = analyze_volatility(df)
    
    # Generate signals with confluence
    signals = generate_confluence_signals(df, zigzag, sr_levels, trend, volatility)
    
    # Build summary
    current_price = df['Close'].iloc[-1]
    summary = build_summary(current_price, zigzag, sr_levels, trend, volatility, signals)
    
    return {
        "dataframe": df,
        "zigzag": zigzag,
        "support_resistance": sr_levels,
        "trend": trend,
        "volatility": volatility,
        "trade_signals": signals,
        "summary": summary,
    }


def find_support_resistance(prices, pivots_result, tolerance=0.015):
    """Find S/R levels with tighter tolerance"""
    peaks = [p["price"] for p in pivots_result["pivots"] if p["type"] == "peak"]
    valleys = [p["price"] for p in pivots_result["pivots"] if p["type"] == "valley"]
    
    resistance_levels = _group_levels(peaks, tolerance)
    support_levels = _group_levels(valleys, tolerance)
    
    current_price = prices[-1]
    
    active_resistance = [r for r in resistance_levels if r > current_price]
    active_support = [s for s in support_levels if s < current_price]
    
    return {
        "resistance": sorted(active_resistance),
        "support": sorted(active_support, reverse=True),
        "all_resistance": sorted(resistance_levels),
        "all_support": sorted(support_levels),
    }


def _group_levels(prices, tolerance):
    """Group similar price levels"""
    if not prices:
        return []
    
    prices = sorted(prices)
    groups = [[prices[0]]]
    
    for price in prices[1:]:
        if abs(price - groups[-1][-1]) / groups[-1][-1] <= tolerance:
            groups[-1].append(price)
        else:
            groups.append([price])
    
    return [np.mean(group) for group in groups]


def analyze_trend(df):
    """Enhanced trend analysis with multiple confirmations"""
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # MA alignment
    ma_bullish = (last['MA_Fast'] > last['MA_Medium'] > last['MA_Slow'])
    ma_bearish = (last['MA_Fast'] < last['MA_Medium'] < last['MA_Slow'])
    
    # Price vs trend MA
    above_trend = last['Close'] > last['MA_Trend']
    
    # MA crossovers
    fast_cross_up = (last['MA_Fast'] > last['MA_Medium']) and (prev['MA_Fast'] <= prev['MA_Medium'])
    fast_cross_down = (last['MA_Fast'] < last['MA_Medium']) and (prev['MA_Fast'] >= prev['MA_Medium'])
    
    # RSI analysis
    rsi_bullish = last['RSI'] > 50
    rsi_oversold = last['RSI'] < OptimizedConfig.RSI_OVERSOLD
    rsi_overbought = last['RSI'] > OptimizedConfig.RSI_OVERBOUGHT
    
    # MACD
    macd_bullish = last['MACD'] > last['MACD_Signal']
    macd_cross_up = (last['MACD'] > last['MACD_Signal']) and (prev['MACD'] <= prev['MACD_Signal'])
    macd_cross_down = (last['MACD'] < last['MACD_Signal']) and (prev['MACD'] >= prev['MACD_Signal'])
    
    # ADX trend strength
    strong_trend = last['ADX'] > 25
    
    # Determine overall trend
    if ma_bullish and above_trend:
        overall = "Strong Uptrend"
    elif ma_bearish and not above_trend:
        overall = "Strong Downtrend"
    elif above_trend:
        overall = "Uptrend"
    elif not above_trend:
        overall = "Downtrend"
    else:
        overall = "Sideways"
    
    return {
        "overall": overall,
        "ma_aligned_bullish": ma_bullish,
        "ma_aligned_bearish": ma_bearish,
        "above_trend_ma": above_trend,
        "fast_cross_up": fast_cross_up,
        "fast_cross_down": fast_cross_down,
        "rsi_bullish": rsi_bullish,
        "rsi_oversold": rsi_oversold,
        "rsi_overbought": rsi_overbought,
        "macd_bullish": macd_bullish,
        "macd_cross_up": macd_cross_up,
        "macd_cross_down": macd_cross_down,
        "strong_trend": strong_trend,
        "adx": last['ADX'],
    }


def analyze_volatility(df):
    """Volatility analysis"""
    last = df.iloc[-1]
    
    atr = last['ATR']
    atr_pct = last['ATR_Pct']
    
    # Classify volatility
    if atr_pct > 3:
        level = "Very High"
    elif atr_pct > 2:
        level = "High"
    elif atr_pct > 1:
        level = "Medium"
    else:
        level = "Low"
    
    return {
        "atr": atr,
        "atr_pct": atr_pct,
        "volatility_level": level,
        "bb_width": last['BB_Width'],
    }


def generate_confluence_signals(df, zigzag, sr_levels, trend, volatility):
    """
    Generate signals based on confluence of multiple factors
    Each signal gets a strength score
    """
    signals = []
    last = df.iloc[-1]
    prev = df.iloc[-2]
    current_price = last['Close']
    
    # BUY SIGNALS
    buy_score = 0
    buy_reasons = []
    
    # 1. Oversold RSI + Bullish divergence potential
    if trend['rsi_oversold']:
        buy_score += 2
        buy_reasons.append("RSI Oversold")
    
    # 2. Price near support
    if sr_levels['support'] and current_price <= sr_levels['support'][0] * 1.01:
        buy_score += 2
        buy_reasons.append("Near Support")
    
    # 3. MA crossover
    if trend['fast_cross_up']:
        buy_score += 2
        buy_reasons.append("MA Golden Cross")
    
    # 4. MACD crossover
    if trend['macd_cross_up']:
        buy_score += 2
        buy_reasons.append("MACD Bullish Cross")
    
    # 5. Bollinger Band bounce
    if current_price < last['BB_Lower']:
        buy_score += 1
        buy_reasons.append("BB Lower Touch")
    
    # 6. Volume confirmation
    if last['Volume_Ratio'] > 1.5:
        buy_score += 1
        buy_reasons.append("High Volume")
    
    # 7. Stochastic oversold
    if last['Stoch_K'] < 20:
        buy_score += 1
        buy_reasons.append("Stochastic Oversold")
    
    # 8. Recent valley in zigzag
    if len(zigzag['pivots']) > 0:
        last_pivot = zigzag['pivots'][-1]
        if last_pivot['type'] == 'valley' and (len(df) - last_pivot['index']) < 20:
            buy_score += 1
            buy_reasons.append("Recent Valley")
    
    # SELL SIGNALS
    sell_score = 0
    sell_reasons = []
    
    # 1. Overbought RSI
    if trend['rsi_overbought']:
        sell_score += 2
        sell_reasons.append("RSI Overbought")
    
    # 2. Price near resistance
    if sr_levels['resistance'] and current_price >= sr_levels['resistance'][0] * 0.99:
        sell_score += 2
        sell_reasons.append("Near Resistance")
    
    # 3. MA crossover
    if trend['fast_cross_down']:
        sell_score += 2
        sell_reasons.append("MA Death Cross")
    
    # 4. MACD crossover
    if trend['macd_cross_down']:
        sell_score += 2
        sell_reasons.append("MACD Bearish Cross")
    
    # 5. Bollinger Band rejection
    if current_price > last['BB_Upper']:
        sell_score += 1
        sell_reasons.append("BB Upper Touch")
    
    # 6. Volume confirmation
    if last['Volume_Ratio'] > 1.5:
        sell_score += 1
        sell_reasons.append("High Volume")
    
    # 7. Stochastic overbought
    if last['Stoch_K'] > 80:
        sell_score += 1
        sell_reasons.append("Stochastic Overbought")
    
    # 8. Recent peak in zigzag
    if len(zigzag['pivots']) > 0:
        last_pivot = zigzag['pivots'][-1]
        if last_pivot['type'] == 'peak' and (len(df) - last_pivot['index']) < 20:
            sell_score += 1
            sell_reasons.append("Recent Peak")
    
    # Generate signals based on confluence
    if buy_score >= OptimizedConfig.MIN_CONFLUENCE_SCORE:
        strength = "STRONG" if buy_score >= OptimizedConfig.STRONG_CONFLUENCE_SCORE else "MEDIUM"
        signals.append({
            "type": "BUY",
            "strength": strength,
            "score": buy_score,
            "reasons": ", ".join(buy_reasons),
            "price": current_price,
        })
    
    if sell_score >= OptimizedConfig.MIN_CONFLUENCE_SCORE:
        strength = "STRONG" if sell_score >= OptimizedConfig.STRONG_CONFLUENCE_SCORE else "MEDIUM"
        signals.append({
            "type": "SELL",
            "strength": strength,
            "score": sell_score,
            "reasons": ", ".join(sell_reasons),
            "price": current_price,
        })
    
    return signals


def build_summary(current_price, zigzag, sr_levels, trend, volatility, signals):
    """Build analysis summary with enhanced risk management"""
    buy_signals = [s for s in signals if s["type"] == "BUY"]
    sell_signals = [s for s in signals if s["type"] == "SELL"]
    
    # Determine recommendation based on signal scores
    buy_total_score = sum(s['score'] for s in buy_signals)
    sell_total_score = sum(s['score'] for s in sell_signals)
    
    if buy_total_score > sell_total_score and buy_total_score >= OptimizedConfig.MIN_CONFLUENCE_SCORE:
        recommendation = "BUY"
        confidence = min(100, (buy_total_score / 8) * 100)  # Max possible score ~8
    elif sell_total_score > buy_total_score and sell_total_score >= OptimizedConfig.MIN_CONFLUENCE_SCORE:
        recommendation = "SELL"
        confidence = min(100, (sell_total_score / 8) * 100)
    else:
        recommendation = "HOLD"
        confidence = 50.0
    
    # Dynamic stop loss/take profit
    atr = volatility["atr"]
    
    if recommendation == "BUY":
        stop_loss = current_price - (OptimizedConfig.STOP_LOSS_ATR_MULT * atr)
        take_profit = current_price + (OptimizedConfig.TAKE_PROFIT_ATR_MULT * atr)
        trailing_stop = current_price - (OptimizedConfig.TRAILING_STOP_ATR_MULT * atr)
    elif recommendation == "SELL":
        stop_loss = current_price + (OptimizedConfig.STOP_LOSS_ATR_MULT * atr)
        take_profit = current_price - (OptimizedConfig.TAKE_PROFIT_ATR_MULT * atr)
        trailing_stop = current_price + (OptimizedConfig.TRAILING_STOP_ATR_MULT * atr)
    else:
        stop_loss = current_price - (OptimizedConfig.STOP_LOSS_ATR_MULT * atr)
        take_profit = current_price + (OptimizedConfig.TAKE_PROFIT_ATR_MULT * atr)
        trailing_stop = None
    
    risk = abs(current_price - stop_loss)
    reward = abs(take_profit - current_price)
    risk_reward_ratio = reward / max(risk, 0.01)
    
    return {
        "current_price": current_price,
        "recommendation": recommendation,
        "confidence": round(confidence, 1),
        "buy_score": buy_total_score,
        "sell_score": sell_total_score,
        "trend": trend["overall"],
        "volatility": volatility["volatility_level"],
        "nearest_support": sr_levels["support"][0] if sr_levels["support"] else None,
        "nearest_resistance": sr_levels["resistance"][0] if sr_levels["resistance"] else None,
        "stop_loss": round(stop_loss, 2),
        "take_profit": round(take_profit, 2),
        "trailing_stop": round(trailing_stop, 2) if trailing_stop else None,
        "risk_reward_ratio": round(risk_reward_ratio, 2),
        "num_pivots": len(zigzag["pivots"]),
    }
