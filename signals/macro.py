# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import yfinance as yf
import FinanceDataReader as fdr
import pandas_datareader.data as web
from config import VIX_KILLSWITCH, VIX_CONFIDENCE_BASE, TIPS_TICKER, SOFR_SAFE_HAVEN

def is_kr_ticker(ticker):
    return str(ticker)[0].isdigit()

def get_macro_expected_returns(tickers, lookback_days=252):
    """
    Fetches macroeconomic data from FRED, calculates recent Z-Scores,
    and translates them into expected returns (Q_macro views).
    """
    print("[MACRO] Fetching global macro data from FRED...")
    
    try:
        macro_df = web.DataReader(['DEXKOUS'], 'fred', start='2024-01-01')
        macro_df = macro_df.ffill()
        
        recent_data = macro_df.tail(lookback_days)
        z_scores = (recent_data.iloc[-1] - recent_data.mean()) / recent_data.std()
        
        usdkrw_z = z_scores['DEXKOUS'] if not np.isnan(z_scores['DEXKOUS']) else 0
        print(f"   -> USDKRW Z-Score: {usdkrw_z:.2f} (Higher = KRW weakness = KR equity headwind)")
        
        # Scalar: Penalty of -5% return expectation per +1.0 Z-score
        kr_macro_view = -1.0 * usdkrw_z * 0.05 
        
    except Exception as e:
        print(f"[WARNING] FRED data fetch failed: {e}")
        kr_macro_view = 0.0
        
    q_macro = pd.Series(0.0, index=tickers)
    for ticker in tickers:
        if is_kr_ticker(ticker):
            q_macro[ticker] = kr_macro_view # Apply heavy FX penalty to KR equities
        else:
            q_macro[ticker] = 0.0 # US equities remain neutral (for now)
            
    return q_macro

def build_dynamic_segment_map(ticker_list):
    """Categorize the seleceted tickers to Growth/Value sector"""
    segment_map = {}
    
    kr_sector_dict = {}
    try:
        kr_listing = fdr.StockListing('KRX')
        if 'Sector' in kr_listing.columns:
            kr_sector_dict = kr_listing.set_index('Code')['Sector'].to_dict()
    except Exception as e:
        print(f"⚠️ KRX 업종 데이터 수집 실패: {e}")

    growth_kw = ['소프트웨어', '반도체', 'IT', '바이오', '제약', '게임', '의료', '통신장비', '전자기기']
    value_kw = ['은행', '금융', '보험', '증권', '건설', '철강', '화학', '에너지', '조선', '유통', '음식료', '지주', '유틸리티']
    
    for t in ticker_list:
        if is_kr_ticker(t):
            clean_t = "".join([c for c in str(t) if c.isdigit()]).zfill(6)
            sector_kr = str(kr_sector_dict.get(clean_t, 'Unknown'))
            
            if any(k in sector_kr for k in growth_kw):
                segment_map[t] = 'Growth'
            elif any(k in sector_kr for k in value_kw):
                segment_map[t] = 'Value'
            else:
                segment_map[t] = 'Unknown'
                
        else:
            try:
                sector_us = yf.Ticker(t).info.get('sector', 'Unknown')
                if sector_us in ['Technology', 'Communication Services', 'Consumer Cyclical', 'Healthcare']:
                    segment_map[t] = 'Growth'
                elif sector_us in ['Financial Services', 'Energy', 'Utilities', 'Consumer Defensive', 'Real Estate', 'Basic Materials', 'Industrials']:
                    segment_map[t] = 'Value'
                else:
                    segment_map[t] = 'Unknown'
            except:
                segment_map[t] = 'Unknown'
                
    return segment_map

def get_macro_signals():
    """
    Phase 1-B: VIX Kill-switch and TIPS Sensitivity.
    Returns a dictionary of adjustments for the optimization engine.
    """
    # 1. Fetch Macro Data (VIX and 10Y TIPS)
    # ^VIX for volatility, TIP for real-rate proxy
    macro_data = yf.download(["^VIX", TIPS_TICKER], period="5d", auto_adjust=True)['Close']
    
    current_vix = macro_data["^VIX"].iloc[-1]
    current_tips = macro_data[TIPS_TICKER].iloc[-1]
    prev_tips = macro_data[TIPS_TICKER].iloc[-2]
    
    # 2. VIX Kill-Switch Logic
    kill_switch_active = current_vix >= VIX_KILLSWITCH
    
    # 3. VIX Confidence Scalar Calculation
    # scalar = 1 + max(0, (VIX - 20) / 20)
    vix_scalar = 1.0 + max(0, (current_vix - VIX_CONFIDENCE_BASE) / 20.0)
    
    # 4. TIPS Sensitivity (Real Rate Spike)
    # If TIP ETF price drops, real rates are rising (inverse relationship)
    # Threshold: A 1% drop in TIP price in a single day is a significant spike
    tips_rate_spike = (current_tips / prev_tips) < 0.99
    
    return {
        "vix_level": current_vix,
        "vix_scalar": vix_scalar,
        "kill_switch": kill_switch_active,
        "tilt_to_quality": tips_rate_spike
    }

def apply_macro_filters(views, macro_signals):
    """
    Adjusts tactical views based on macro risk filters.
    """
    adjusted_views = views.copy()
    
    # Global Kill-Switch: Move all assets to cash/bonds
    if macro_signals.get("global_kill_switch", False):
        print("🚨 [GLOBAL KILL-SWITCH]")
        adjusted_views[:] = 0  
        if SOFR_SAFE_HAVEN in adjusted_views.columns:
            adjusted_views[SOFR_SAFE_HAVEN] = 1.0
            
    # KR Kill-Switch: surge USDKRW
    elif macro_signals.get("kr_kill_switch", False):
        print("☔️ [FX KILL-SWITCH]")
        for asset in adjusted_views.columns:
            if is_kr_ticker(asset):
                adjusted_views[asset] = 0
            
    # If Real Rates spike, penalize Growth/Agri and reward Quality
    if macro_signals["tilt_to_quality"]:
        print("🛡️ [QUALITY TILT]")
        dynamic_segment_map = build_dynamic_segment_map(adjusted_views.index.tolist())
        for asset in adjusted_views.index:
            segment = dynamic_segment_map.get(asset, "Unknown")
            if segment in ["Growth", "Tech", "IT", "Consumer Discretionary"]:
                adjusted_views[asset] *= 0.5
            elif segment in ["Quality", "Value", "Defensive", "Energy", "Financials", "Utilities"]:
                adjusted_views[asset] *= 1.5
            else:
                adjusted_views[asset] *= 0.9
            
    return adjusted_views