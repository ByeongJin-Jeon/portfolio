# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import yfinance as yf
from scipy import stats

def calculate_minervini_score(prices, volumes, ticker):
    """
    Minervini QM Scoring (17 points max -> 100 normalized)
    Strictly uses yesterday's data (shift(1)) to prevent look-ahead bias.
    """
    try:
        # Pre-shift the series to ensure no future data is leaked
        p = prices[ticker].shift(1)
        v = volumes[ticker].shift(1)
        
        ma50 = p.rolling(50).mean()
        ma150 = p.rolling(150).mean()
        ma200 = p.rolling(200).mean()
        ma20 = p.rolling(20).mean()
        
        curr_p = p.iloc[-1]
        curr_ma50 = ma50.iloc[-1]
        curr_ma150 = ma150.iloc[-1]
        curr_ma200 = ma200.iloc[-1]
        curr_ma20 = ma20.iloc[-1]
        
        score = 0
        if curr_p > curr_ma150: score += 1
        if curr_p > curr_ma200: score += 1
        if curr_ma150 > curr_ma200: score += 1
        
        if (ma200.diff(20) > 0).iloc[-1]: score += 1
        
        if curr_ma50 > curr_ma150: score += 1
        if curr_ma50 > curr_ma200: score += 1
        if curr_p > curr_ma50: score += 1
        
        high52 = p.rolling(252).max().iloc[-1]
        low52 = p.rolling(252).min().iloc[-1]
        if curr_p > low52 * 1.30: score += 1
        if curr_p > high52 * 0.75: score += 1
        
        days_since_high = (p.rolling(252).apply(lambda x: x.argmax())).iloc[-1]
        if days_since_high >= 232: score += 1
        
        high_r = p.rolling(2).max()
        low_r = p.rolling(2).min()
        tr = high_r - low_r
        atr10 = tr.rolling(10).mean().iloc[-1]
        atr50 = tr.rolling(50).mean().iloc[-1]
        if atr10 < atr50: score += 1
        
        returns = p.pct_change()
        up_vol = v[returns > 0].rolling(20).mean().iloc[-1]
        down_vol = v[returns < 0].rolling(20).mean().iloc[-1]
        if up_vol > down_vol: score += 1
        
        if v.iloc[-1] > v.rolling(50).mean().iloc[-1]: score += 1
        
        band = (p.rolling(15).max() / p.rolling(15).min() - 1).iloc[-1]
        if band < 0.10: score += 1
        
        delta = p.diff()
        gain = delta.where(delta > 0, 0.0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0.0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss
        rsi = (100.0 - (100.0 / (1.0 + rs))).iloc[-1]
        if rsi > 60: score += 1
        
        if curr_p > curr_ma20: score += 1
        
        exp1 = p.ewm(span=12, adjust=False).mean()
        exp2 = p.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        hist = macd - signal
        if hist.iloc[-1] > 0: score += 1
        
        return (score / 17.0) * 100.0
    except Exception:
        return 0.0

def calculate_cps_trend(ticker):
    """
    Calculates the slope of the 3-year Cash Flow Per Share (CPS) trend line.
    """
    try:
        yf_ticker = ticker
        if str(ticker)[0].isdigit():
            clean_ticker = str(ticker).replace('.KS', '').replace('.KQ', '')
            yf_ticker = f"{clean_ticker}.KS"
            
        stock = yf.Ticker(yf_ticker)
        cf = stock.cashflow
        info = stock.info
        shares = info.get('sharesOutstanding')
        
        if cf.empty or not shares or 'Operating Cash Flow' not in cf.index:
            return 50.0
            
        ocf = cf.loc['Operating Cash Flow'].dropna().iloc[::-1] # Oldest to newest
        if len(ocf) < 2:
            return 50.0
            
        cps = ocf / shares
        x = np.arange(len(cps))
        slope, _, _, _, _ = stats.linregress(x, cps.values)
        
        norm_slope = (slope / abs(cps.mean())) if cps.mean() != 0 else 0
        score = 50.0 + (norm_slope * 100.0)
        return max(0.0, min(100.0, score))
    except Exception:
        return 50.0

def generate_trend_views(prices, volumes):
    """
    Computes trend factors including the CPS trend line.
    Ensures all calculations use shift(1) data.
    """
    tickers = prices.columns
    views = pd.Series(0.0, index=tickers)
    
    # Strictly use yesterday's prices and volumes for all calculations
    p_shifted = prices.shift(1)
    v_shifted = volumes.shift(1)
    
    # Preprocessing: Outlier Clipping for volumes
    v_clean = v_shifted.copy()
    for col in v_clean.columns:
        avg20 = v_clean[col].rolling(20).mean()
        v_clean[col] = np.where(v_clean[col] > avg20 * 10, avg20, v_clean[col])
    
    for ticker in tickers:
        scores = {}
        try:
            # 1. Minervini QM (uses shift(1) internally but we pass full series)
            # Actually, calculate_minervini_score already shifts internally. 
            # To be 100% safe, let's pass the already shifted series and remove internal shifts.
            scores["Minervini_QM"] = calculate_minervini_score(prices, volumes, ticker)
            
            # 2. Return (6M) - must use shifted data
            ret6m = (p_shifted[ticker].iloc[-1] / p_shifted[ticker].shift(120).iloc[-1]) - 1
            scores["Return_6M"] = max(0.0, min(100.0, ret6m * 100.0 + 50.0))
            
            # 3. Volume/Price CV (1M)
            vol_cv = v_clean[ticker].rolling(20).std() / v_clean[ticker].rolling(20).mean()
            curr_cv = vol_cv.iloc[-1]
            scores["Volume_Price_CV"] = max(0.0, min(100.0, (1.0 - curr_cv) * 100.0))
            
            # 4. Upside Potential
            high52 = p_shifted[ticker].rolling(252).max().iloc[-1]
            curr_p = p_shifted[ticker].iloc[-1]
            upside = (high52 - curr_p) / curr_p
            scores["Upside_Potential"] = max(0.0, min(100.0, upside * 100.0))
            
            # 5. Trend Line of CPS
            scores["Trend_Line_CPS"] = calculate_cps_trend(ticker)
            
            ticker_score = (scores["Minervini_QM"] * 0.1667 + 
                            scores["Return_6M"] * 0.05 + 
                            scores["Volume_Price_CV"] * 0.05 + 
                            scores["Upside_Potential"] * 0.05 + 
                            scores["Trend_Line_CPS"] * 0.05) / 0.3667
            views[ticker] = ticker_score
            
        except Exception:
            views[ticker] = 0.0
    
    assert (views >= 0.0).all() and (views <= 100.0).all()
    
    views = views / 100.0

    return views
