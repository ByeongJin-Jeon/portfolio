# -*- coding: utf-8 -*-
import vectorbt as vbt
import pandas as pd
from config import MA_PERIODS, ENVELOPE_PERIOD, ENVELOPE_BAND

def generate_trend_views(prices):
    """
    Phase 1-A: MA Alignment & Envelope logic.
    Returns a 'View Strength' between -1 and 1 for each asset.
    """
    # 1. Moving Averages
    mas = {f"MA{p}": vbt.MA.run(prices, p).ma for p in MA_PERIODS}
    
    # 2. Alignment Logic: High conviction if 5 > 22 > 60 > 182
    bull_align = (mas['MA5'] > mas['MA22']) & (mas['MA22'] > mas['MA60']) & (mas['MA60'] > mas['MA182'])
    
    # 3. Envelope Filter (Mean Reversion)
    central_ma = mas[f'MA{ENVELOPE_PERIOD}']
    upper_band = central_ma * (1 + ENVELOPE_BAND)
    overbought = prices > upper_band
    
    # Logic: Bullish view capped/reversed if overbought
    views = bull_align.astype(float)
    views[overbought] *= 0.5 # Dampen confidence if price is > +10% envelope
    
    return views