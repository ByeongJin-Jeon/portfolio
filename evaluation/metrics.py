# -*- coding: utf-8 -*-
import numpy as np

def calculate_resilience_suite(vbt_pf):
    """
    Computes specialized metrics for crisis-management evaluation.
    """
    # 1. Max Drawdown (MDD) - The maximum peak-to-trough decline
    mdd = vbt_pf.max_drawdown() * 100
    
    # 2. Ulcer Index (UI) - Measures the depth AND duration of drawdowns
    # UI = sqrt(mean(drawdown^2))
    drawdowns = vbt_pf.drawdowns.drawdown()
    ui = np.sqrt(np.mean(np.square(drawdowns))) * 100
    
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