# -*- coding: utf-8 -*-
import pandas as pd
from config import MAX_ASSETS, CSV_ENCODING

def select_final_portfolio(bl_weights, liquidity_caps):
    """
    Applies liquidity caps and selects the Top 10 assets.
    Ensures data types are aligned for scalar comparison.
    """
    # 1. Convert DataFrame to Series if necessary
    # Riskfolio returns a DataFrame; we take the first column to get a Series
    if isinstance(bl_weights, pd.DataFrame):
        final_weights = bl_weights.iloc[:, 0].copy()
    else:
        final_weights = bl_weights.copy()

    # 2. Apply Liquidity Constraints
    for asset in final_weights.index:
        if asset in liquidity_caps.index:
            # Both sides are now scalars, so min() works flawlessly
            final_weights.loc[asset] = min(
                float(final_weights.loc[asset]), 
                float(liquidity_caps.loc[asset])
            )
            
    # 3. Re-normalize weights to sum to 1.0
    if final_weights.sum() > 0:
        final_weights = final_weights / final_weights.sum()
    
    # 4. Select Top N
    top_n = final_weights.sort_values(ascending=False).head(MAX_ASSETS)
    
    return top_n

def export_portfolio(weights, path):
    """Outputs the final allocation to terminal and CSV."""
    print("\n--- GEOPOLITICALLY RESILIENT PORTFOLIO (TOP 10) ---")
    print(weights)
    weights.to_csv(path, encoding=CSV_ENCODING)