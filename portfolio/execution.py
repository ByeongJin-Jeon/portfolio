# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import yfinance as yf

def _calculate_single_asset_limit(ticker, n=20, k=3.0):
    """
    [Internal Engine] Calculates the Chandelier Exit lower bound (sleep-trading limit buy price) for a single asset.
    n: Period to find the safety pin (highest high)
    k: Shield thickness (ATR multiplier)
    """
    # For Korean stock codes (starting with numbers), append .KS for yfinance recognition
    yf_ticker = f"{ticker}.KS" if str(ticker)[0].isdigit() else ticker
    
    try:
        # 60 days of data is enough to calculate 20-day high/volatility!
        df = yf.download(yf_ticker, period="60d", progress=False)
        
        if df.empty:
            return None, None
            
        # Flatten columns in case of MultiIndex in recent yfinance versions (safety measure)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
            
        # 🚨 [VERY IMPORTANT] If intraday data is mixed, values change in real-time!
        # To place a scheduled buy order, we must fix it based on 'yesterday (past)' data.
        # That's why we use shift(1) to base it on data up to yesterday.
        df['High_Shift'] = df['High'].shift(1)
        df['Low_Shift'] = df['Low'].shift(1)
        df['Close_Shift'] = df['Close'].shift(1)
        
        # 1️⃣ Safety Pin: Recent n-day highest high
        rolling_max = df['High_Shift'].rolling(window=n).max().iloc[-1]
        
        # 2️⃣ Volatility (ATR): True range considering daily amplitude and gaps
        high_low = df['High_Shift'] - df['Low_Shift']
        high_pc = (df['High_Shift'] - df['Close_Shift'].shift(1)).abs()
        low_pc = (df['Low_Shift'] - df['Close_Shift'].shift(1)).abs()
        
        tr = pd.concat([high_low, high_pc, low_pc], axis=1).max(axis=1)
        atr = tr.rolling(window=n).mean().iloc[-1]  # Average volatility over recent n days
        
        # 3️⃣ Final Line of Defense (Sleep-trading limit buy price)
        limit_price = min(rolling_max - (k * atr), current_price)
        current_price = df['Close'].iloc[-1] # Current price (or most recent closing price)
        
        return current_price, limit_price
        
    except Exception as e:
        print(f"   -> ⚠️ [Error] Failed to load data for {ticker}: {e}")
        return None, None


def generate_execution_plan(final_weights, n_lookback=20, k_value=3.0):
    """
    [Sleep-Trading Planner 💤]
    Receives the final portfolio weights and generates limit prices for all assets.
    """
    print(f"\n🌙 [SLEEP-TRADING] Calculating tonight's scheduled buy prices... (Safety Pin: {n_lookback} days, Shield: {k_value}x)")
    
    execution_targets = []
    
    for ticker, weight in final_weights.items():
        # Skip assets with zero or negligible weights!
        if weight <= 0.001: 
            continue
            
        current_p, limit_p = _calculate_single_asset_limit(ticker, n=n_lookback, k=k_value)
        
        if current_p is not None and limit_p is not None:
            execution_targets.append({
                "Ticker": ticker,
                "Target_Weight": f"{weight*100:.2f}%",
                "Current_Price": round(current_p, 2),
                "Limit_Buy_Price": round(limit_p, 2),
                "Drop_Needed": f"{((limit_p / current_p) - 1) * 100:.2f}%" # % drop required from current price
            })
            
    exec_df = pd.DataFrame(execution_targets)
    return exec_df