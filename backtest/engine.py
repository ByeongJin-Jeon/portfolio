# -*- coding: utf-8 -*-
import vectorbt as vbt
import pandas as pd
import numpy as np
from config import BACKTEST_SCENARIOS, BACKTEST_INITIAL_CAPITAL, BACKTEST_COMMISSION

class ResilientBacktester:
    """
    [WALK-FORWARD] Executes monthly rolling rebalancing simulations.
    No Look-Ahead Bias allowed!
    """
    def __init__(self, price_data, strategy_func=None):
        self.prices = price_data
        # strategy_func: A function that takes 'past_prices' and returns 'optimal_weights'
        self.strategy_func = strategy_func

    def run_single_scenario(self, scenario_name, static_weights=None):
        """Runs a specific crisis window using either Walk-Forward or Static mode."""
        print(f"\n[SCENARIO] Initiating Time Machine for '{scenario_name}'...")
        start, end = BACKTEST_SCENARIOS[scenario_name]
        
        date_subset = self.prices.loc[start:end] if end else self.prices.loc[start:]
        available_assets = date_subset.columns[date_subset.iloc[0].notnull()]
        asset_subset = date_subset[available_assets]

        if asset_subset.empty:
            print(f"   -> [WARNING] No data available for {scenario_name}. Skipping.")
            return None

        # ---------------------------------------------------------
        # 1. WALK-FORWARD MODE (Monthly Rebalancing)
        # ---------------------------------------------------------
        if self.strategy_func is not None:
            print("   -> [WALK-FORWARD] Monthly Rebalancing Activated (No Look-Ahead Bias).")
            print("   -> [INFO] Running the optimizer for EVERY month. Grab a coffee! ☕")
            
            # Extract End-of-Month dates
            try:
                monthly_dates = asset_subset.resample('ME').last().index # pandas >= 2.2
            except ValueError:
                monthly_dates = asset_subset.resample('M').last().index  # pandas < 2.2
            
            # Create a DataFrame of NaNs to hold our target weights.
            # vectorbt will ONLY trade on days with non-NaN values! (Perfect for monthly rebalancing)
            target_weights_df = pd.DataFrame(np.nan, index=asset_subset.index, columns=asset_subset.columns)
            
            for i, current_date in enumerate(monthly_dates):
                # Print progress on the same line
                print(f"      * Rebalancing {current_date.strftime('%Y-%m')} ({i+1}/{len(monthly_dates)})...", end="\r")
                
                # THE GOLDEN RULE: Cut data exactly at current_date (NO FUTURE DATA!)
                past_prices = self.prices.loc[:current_date]
                
                try:
                    # Call your brain (Strategy Pipeline)
                    weights = self.strategy_func(past_prices)
                    
                    # Map weights to available assets and normalize
                    final_assets = [a for a in weights.index if a in available_assets]
                    w = weights.loc[final_assets]
                    if w.sum() > 0:
                        w = w / w.sum()
                    
                    # Inject weights into the matrix for this specific rebalance date
                    for asset in w.index:
                        target_weights_df.loc[current_date, asset] = w[asset]
                        
                except Exception as e:
                    # If optimizer fails (e.g., extreme crisis), go 100% cash (weights = 0)
                    target_weights_df.loc[current_date] = 0.0
            
            print(f"\n      * [SUCCESS] Walk-Forward trajectory built for {scenario_name}!")
            
            # Execute the trades!
            pf = vbt.Portfolio.from_orders(
                close=asset_subset,
                size=target_weights_df,
                size_type='target_percent',
                init_cash=BACKTEST_INITIAL_CAPITAL,
                fees=BACKTEST_COMMISSION,
                freq='D',
                cash_sharing=True
            )
            return pf

        # ---------------------------------------------------------
        # 2. STATIC MODE (Buy & Hold Fallback)
        # ---------------------------------------------------------
        else:
            print("   -> [STATIC] Using Static Weights (Buy & Hold). Warning: Look-Ahead Bias!")
            if static_weights is None:
                print("   -> [ERROR] No static weights provided.")
                return None
                
            final_assets = [a for a in static_weights.index if a in available_assets]
            new_weights = static_weights.loc[final_assets]
            new_weights = new_weights / new_weights.sum()
            new_weights = new_weights.values.flatten()

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

    def run_all_scenarios(self, static_weights=None):
        """Runs the engine across all windows in config."""
        results = {}
        for name in BACKTEST_SCENARIOS.keys():
            results[name] = self.run_single_scenario(name, static_weights)
        return results