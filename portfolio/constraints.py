# -*- coding: utf-8 -*-
import pandas as pd
from config import LIQUIDITY_WINDOW, MAX_WEIGHT_SINGLE

def calculate_liquidity_caps(volume_data, price_data, total_portfolio_value):
    """
    Sets a Weight Constraint with a 'Panic Floor' to prevent forced divestment.
    """
    # 1. Calculate current short-term liquidity
    avg_volume_short = volume_data.tail(LIQUIDITY_WINDOW).mean()
    
    # 2. Calculate the 'Panic Floor' (10th percentile of the last 252 trading days)
    # This represents a 'bad but normal' liquidity day, rather than a total freeze.
    volume_floor = volume_data.tail(252).quantile(0.10)
    
    # Use the higher of the two to prevent the cap from dropping to zero
    effective_volume = pd.concat([avg_volume_short, volume_floor], axis=1).max(axis=1)
    
    avg_price = price_data.tail(LIQUIDITY_WINDOW).mean()
    
    # 3. Dollar Volume Capacity (Assuming 1% daily participation)
    capacity_usd = effective_volume * avg_price * 0.01
    
    # 4. Final weight limits per asset
    liquidity_weights = capacity_usd / total_portfolio_value
    
    # Clip by the hard ceiling defined in config
    final_caps = liquidity_weights.clip(upper=MAX_WEIGHT_SINGLE)
    
    return final_caps