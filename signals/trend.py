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
    for p in MA_PERIODS:
        ma_df = vbt.MA.run(prices, p).ma
        
        # vectorbt adds the window 'p' as a top-level column index.
        # we drop it so that MA5, MA22, etc., all have identical 'Ticker' columns.
        if isinstance(ma_df.columns, pd.MultiIndex):
            ma_df.columns = ma_df.columns.droplevel(0)
        
        mas[f"MA{p}"] = ma_df

    # 2. Alignment Logic: Now identically labeled, so comparison works
    bull_align = (mas['MA5'] > mas['MA22']) & (mas['MA22'] > mas['MA60'])
    bear_align = (mas['MA5'] < mas['MA22']) & (mas['MA22'] < mas['MA60'])

    # 3. Golden/Dead cross with MA5 and MA22
    golden_cross = (mas['MA5'] > mas['MA22']) & (mas['MA5'].shift(1) <= mas['MA22'].shift(1))
    dead_cross = (mas['MA5'] < mas['MA22']) & (mas['MA5'].shift(1) >= mas['MA22'].shift(1))

    # 4. Envelope Filter (Mean Reversion)
    central_ma = mas[f'MA{ENVELOPE_PERIOD}']
    upper_band = central_ma * (1 + ENVELOPE_BAND)
    lower_band = central_ma * (1 - ENVELOPE_BAND)
    
    overbought = prices > upper_band
    oversold = prices < lower_band
    
    # 4. View Strength Logic
    views = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    views += bull_align.astype(float) * 1.0
    views += bear_align.astype(float) * -1.0

    views += golden_cross.astype(float) * 0.5
    views += dead_cross.astype(float) * -0.5

    views += overbought.astype(float) * -1.0
    views += oversold.astype(float) * 1.0
    
    return views