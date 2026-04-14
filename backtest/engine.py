# -*- coding: utf-8 -*-
import vectorbt as vbt
import pandas as pd
from config import BACKTEST_SCENARIOS, BACKTEST_INITIAL_CAPITAL, BACKTEST_COMMISSION

class ResilientBacktester:
    """
    Executes multi-scenario simulations to validate geopolitical resilience.
    """
    def __init__(self, price_data):
        self.prices = price_data

    def run_single_scenario(self, weights, scenario_name):
        """Runs a specific crisis window (e.g., MIDEAST_2026)."""
        start, end = BACKTEST_SCENARIOS[scenario_name]
        
        date_subset = self.prices.loc[start:end] if end else self.prices.loc[start:]
        
        available_assets = date_subset.columns[date_subset.iloc[0].notnull()]
        final_assets = [a for a in weights.index if a in available_assets]

        if not final_assets:
            print(f"⚠️  Skipping '{scenario_name}': No assets from your Top 10 existed during this period.")
            return None
        
        new_weights = weights.loc[final_assets]
        new_weights = new_weights / new_weights.sum()
        new_weights = new_weights.values.flatten()

        asset_subset = date_subset[final_assets]
        
        pf = vbt.Portfolio.from_orders(
            close=asset_subset,
            size=new_weights,
            size_type='target_percent',
            init_cash=BACKTEST_INITIAL_CAPITAL,
            fees=BACKTEST_COMMISSION,
            freq='D',
            cash_sharing=True
        )
        return pf

    def run_all_scenarios(self, weights):
        """Runs the engine across all windows in config."""
        results = {name: self.run_single_scenario(weights, name) for name in BACKTEST_SCENARIOS.keys()}
        return results

def run_scenario_backtest(price_data, weights, scenario_name):
    """Bridge function for main.py orchestration."""
    tester = ResilientBacktester(price_data)
    return tester.run_all_scenarios(weights, scenario_name)