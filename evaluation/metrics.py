# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd

def calculate_resilience_suite(vbt_pf):
    """
    Computes specialized metrics for crisis-management evaluation.
    """
    dd_attr = vbt_pf.drawdown
    
    if callable(dd_attr):
        dd_data = dd_attr()
    else:
        dd_data = dd_attr

    if hasattr(dd_data, 'to_pandas'):
        dd_series = dd_data.to_pandas()
    else:
        dd_series = pd.Series(dd_data)
    
    # 1. Max Drawdown (MDD) - The maximum peak-to-trough decline
    mdd = dd_series.min() * 100
    
    # 2. Ulcer Index (UI) - Measures the depth AND duration of drawdowns
    # UI = sqrt(mean(drawdown^2))
    ui = np.sqrt(np.mean(np.square(dd_series))) * 100
    
    # 3. Serenity Ratio - A holistic measure of 'stress-free' return
    # Formula: (Annualized Return - RF) / (Ulcer Index * Max Drawdown)
    ann_return = vbt_pf.annualized_return()
    serenity_ratio = ann_return / (ui * abs(mdd) / 100) if ui > 0 else 0
    
    # 4. Calmar Ratio - Return vs. MDD
    calmar = vbt_pf.calmar_ratio()
    
    return {
        "Annualized Return (%)": ann_return * 100,
        "Max Drawdown (%)": mdd,
        "Ulcer Index": ui,
        "Serenity Ratio": serenity_ratio,
        "Calmar Ratio": calmar
    }