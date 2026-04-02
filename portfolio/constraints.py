# -*- coding: utf-8 -*-
import pandas as pd
from config import LIQUIDITY_WINDOW, MAX_WEIGHT_SINGLE

def calculate_liquidity_caps(volume_data, price_data, total_portfolio_value):
    """
    Sets a Weight Constraint based on the average trading volume.
    Formula: Max Weight = (Avg Volume * Price * 0.01) / Total Portfolio Value
    (Assuming we don't want to be more than 1% of daily volume)
    """
    avg_volume = volume_data.tail(LIQUIDITY_WINDOW).mean()
    avg_price = price_data.tail(LIQUIDITY_WINDOW).mean()
    
    # Dollar Volume Capacity (1% of daily volume)
    capacity_usd = avg_volume * avg_price * 0.01
    
    # Weight limits per asset
    liquidity_weights = capacity_usd / total_portfolio_value
    
    # Ensure it doesn't exceed the hard ceiling in config
    final_caps = liquidity_weights.clip(upper=MAX_WEIGHT_SINGLE)
    
    return final_caps