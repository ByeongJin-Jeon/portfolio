# -*- coding: utf-8 -*-
import vectorbt as vbt
import pandas as pd
from config import MA_PERIODS, ENVELOPE_PERIOD, ENVELOPE_BAND

def calculate_rsi(prices, window=14):
    """
    Computes the standard RSI (Relative Strength Index) for the universe.
    Uses Exponential Moving Average (EMA) for institutional-grade smoothing.
    """
    delta = prices.diff()
    
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    
    avg_gain = gain.ewm(com=window-1, min_periods=window).mean()
    avg_loss = loss.ewm(com=window-1, min_periods=window).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi

def generate_trend_views(prices):
    """
    Hybrid Momentum Engine:
    Blends Absolute Momentum (EMA Alignment) with Relative Momentum (RSI Z-Score)."""
    # ---------------------------------------------------------
    # 1. Absolute Momentum (Your original EMA alignment logic!)
    # ---------------------------------------------------------
    ema_5 = prices.ewm(span=5, adjust=False).mean().iloc[-1]
    ema_20 = prices.ewm(span=20, adjust=False).mean().iloc[-1]
    ema_60 = prices.ewm(span=60, adjust=False).mean().iloc[-1]
    
    # +1.0 for perfect bullish alignment, -1.0 for perfect bearish, 0 otherwise
    ema_score = pd.Series(0.0, index=prices.columns)
    ema_score[(ema_5 > ema_20) & (ema_20 > ema_60)] = 1.0
    ema_score[(ema_5 < ema_20) & (ema_20 < ema_60)] = -1.0
    
    # ---------------------------------------------------------
    # 2. Relative Momentum (Cross-Sectional RSI Z-Score)
    # ---------------------------------------------------------
    rsi_df = calculate_rsi(prices, window=14)
    latest_rsi = rsi_df.iloc[-1].dropna()
    
    if latest_rsi.empty:
        print("[WARNING] RSI calculation failed. Returning neutral views.")
        return pd.Series(0.0, index=prices.columns)
        
    rsi_z_scores = (latest_rsi - latest_rsi.mean()) / latest_rsi.std()
    
    # ---------------------------------------------------------
    # 3. Blend & Convert to Expected Returns (Q_trend)
    # ---------------------------------------------------------
    # EMA gives direction (multiplier 1.0), RSI gives extra turbo speed (multiplier 0.5)
    combined_score = (ema_score * 1.0) + (rsi_z_scores * 0.5)
    
    # Convert score to expected return (1.0 score = 5% expectation)
    Q_trend = combined_score * 0.05
    Q_trend = Q_trend.clip(lower=-0.15, upper=0.15)
    
    print(f"   -> Strongest Hybrid Trend: {Q_trend.idxmax()} ({Q_trend.max()*100:.1f}%)")
    print(f"   -> Weakest Hybrid Trend: {Q_trend.idxmin()} ({Q_trend.min()*100:.1f}%)")
    
    return Q_trend