# -*- coding: utf-8 -*-
import vectorbt as vbt
import pandas as pd
from config import MA_PERIODS, ENVELOPE_PERIOD, ENVELOPE_BAND

def generate_trend_views(prices):
    """
    Phase 1-A: MA Alignment & Envelope logic with Label Alignment.
    """
    # 1. Calculate Moving Averages and Force Column Alignment
    mas = {}
    for p in MA_PERIODS: #
        ma_df = vbt.MA.run(prices, p).ma
        
        # vectorbt adds the window 'p' as a top-level column index.
        # we drop it so that MA5, MA22, etc., all have identical 'Ticker' columns.
        if isinstance(ma_df.columns, pd.MultiIndex):
            ma_df.columns = ma_df.columns.droplevel(0)
        
        mas[f"MA{p}"] = ma_df

    # 2. Alignment Logic: Now identically labeled, so comparison works
    bull_align = (mas['MA5'] > mas['MA22']) & \
                 (mas['MA22'] > mas['MA60']) & \
                 (mas['MA60'] > mas['MA182'])
    
    # 3. Envelope Filter (Mean Reversion)
    central_ma = mas[f'MA{ENVELOPE_PERIOD}'] #
    upper_band = central_ma * (1 + ENVELOPE_BAND) #
    
    # Both 'prices' and 'upper_band' now have the same column labels
    overbought = prices > upper_band
    
    # 4. View Strength Logic
    views = bull_align.astype(float)
    views[overbought] *= 0.5 
    
    return views