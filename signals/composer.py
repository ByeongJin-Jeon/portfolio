# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
from signals.trend import generate_trend_views
from signals.macro import get_vix_scalar
from config import MIN_SIGNAL_STRENGTH

def compose_bl_inputs(prices):
    """
    Merges Trend + Macro into Q (Views) and Omega (Uncertainty).
    Implements 'Persistence Filter': Signal must be stable for 3 days.
    """
    raw_views = generate_trend_views(prices)
    
    # 1. Persistence Filter: Only take views that have been stable
    # (Rolling mean of views over 3 days must be high)
    stable_views = raw_views.rolling(window=3).mean()
    
    # 2. Filter by Minimum Strength
    final_q = stable_views.iloc[-1]
    final_q[final_q < MIN_SIGNAL_STRENGTH] = 0
    
    # 3. Macro Dampening
    vix_scalar, kill_switch = get_vix_scalar()
    
    # 4. Construct Omega (Uncertainty)
    # Omega is proportional to the variance of returns scaled by VIX
    # For now, initialized as a diagonal; FF5 residuals will refine this in Step 5a.
    variances = prices.pct_change().var()
    omega_diag = variances * vix_scalar
    
    return final_q, omega_diag, kill_switch