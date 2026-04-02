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

    def run_all_scenarios(self, weights):
        """Runs the engine across 2008, 2020, and 2026 windows."""
        results = {}
        for name, (start, end) in BACKTEST_SCENARIOS.items():
            # Slice data for the specific crisis period
            subset = self.prices.loc[start:end] if end else self.prices.loc[start:]
            
            # Simulate target-weight rebalancing
            pf = vbt.Portfolio.from_orders(
                close=subset,
                size=weights,
                size_type='target_percent',
                init_cash=BACKTEST_INITIAL_CAPITAL,
                fees=BACKTEST_COMMISSION,
                freq='D',
                cash_sharing=True
            )
            results[name] = pf
        return results