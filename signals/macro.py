# -*- coding: utf-8 -*-
import pandas as pd
import yfinance as yf
from config import VIX_KILLSWITCH, VIX_CONFIDENCE_BASE, TIPS_TICKER, SOFR_SAFE_HAVEN

def get_macro_signals():
    """
    Phase 1-B: VIX Kill-switch and TIPS Sensitivity.
    Returns a dictionary of adjustments for the optimization engine.
    """
    # 1. Fetch Macro Data (VIX and 10Y TIPS)
    # ^VIX for volatility, TIP for real-rate proxy
    macro_data = yf.download(["^VIX", TIPS_TICKER], period="5d")['Adj Close']
    
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
    
    # If Kill-Switch is active, force rotation to SOFR/Safe Haven
    if macro_signals["kill_switch"]:
        adjusted_views[:] = 0  # Zero out equity views
        if SOFR_SAFE_HAVEN in adjusted_views.index:
            adjusted_views[SOFR_SAFE_HAVEN] = 1.0
            
    # If Real Rates spike, penalize Growth/Agri and reward Quality
    if macro_signals["tilt_to_quality"]:
        for asset in adjusted_views.index:
            # Logic could be linked to your SEGMENT_MAP in config.py
            pass
            
    return adjusted_views