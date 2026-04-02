# -*- coding: utf-8 -*-
import pandas as pd
from config import MAX_ASSETS, CSV_ENCODING

def select_final_portfolio(bl_weights, liquidity_caps):
    """
    Applies liquidity caps and selects the Top 10 assets by weight.
    """
    # 1. Apply Liquidity Constraints
    final_weights = bl_weights.copy()
    for asset in final_weights.index:
        if asset in liquidity_caps.index:
            final_weights.loc[asset] = min(final_weights.loc[asset], liquidity_caps.loc[asset])
            
    # 2. Re-normalize weights to sum to 1.0
    final_weights = final_weights / final_weights.sum()
    
    # 3. Select Top N
    top_n = final_weights.sort_values(ascending=False).head(MAX_ASSETS)
    
    return top_n

def export_portfolio(weights, path):
    """Outputs the final allocation to terminal and CSV."""
    print("\n--- GEOPOLITICALLY RESILIENT PORTFOLIO (TOP 10) ---")
    print(weights)
    weights.to_csv(path, encoding=CSV_ENCODING)