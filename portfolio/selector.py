# -*- coding: utf-8 -*-
import pandas as pd
from config import MAX_ASSETS, CSV_ENCODING

def select_final_portfolio(bl_weights, liquidity_caps, kr_floor=0.06):
    """Applies liquidity caps and selects the Top 10 assets globally based on optimized weight."""
    weights = bl_weights.iloc[:, 0] if isinstance(bl_weights, pd.DataFrame) else bl_weights.copy()

    for asset in weights.index:
        if asset in liquidity_caps.index:
            weights.loc[asset] = min(float(weights.loc[asset]), float(liquidity_caps.loc[asset]))
    
    top_assets = weights.nlargest(MAX_ASSETS)

    final_portfolio = top_assets / top_assets.sum()
    
    return final_portfolio

def export_portfolio(weights, path):
    """Outputs the final allocation to terminal and CSV."""
    active_weights = weights[weights > 0].sort_values(ascending=False)
    active_weights.to_csv(path, encoding=CSV_ENCODING)