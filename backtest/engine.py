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
        
        # 1. Slice dates for the scenario window
        date_subset = self.prices.loc[start:end] if end else self.prices.loc[start:]
        
        # 해당 기간에 데이터가 하나라도 NaN인 종목은 제외!
        available_assets = date_subset.columns[date_subset.iloc[0].notnull()]
        final_assets = [a for a in weights.index if a in available_assets]

        if not final_assets:
            print(f"⚠️  Skipping '{scenario_name}': No assets from your Top 10 existed during this period.")
            # 빈 결과물이나 에러를 대신할 수 있는 Dummy 객체 혹은 None 리턴
            return None
        
        # 비중 재조정 (선택된 애들끼리 다시 100% 채우기)
        new_weights = weights.loc[final_assets]
        new_weights = new_weights / new_weights.sum()
        new_weights = new_weights.values.flatten()

        asset_subset = date_subset[final_assets]
        
        # 3. Simulate target-weight rebalancing
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