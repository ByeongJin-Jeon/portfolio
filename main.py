# -*- coding: utf-8 -*-
from data.loader import load_from_cache
from signals.composer import compose_bl_inputs
from portfolio.factor_loading import calculate_idiosyncratic_risk
from optimization.hrp import get_hrp_prior_weights
from optimization.black_litterman import construct_bl_model
from portfolio.selector import select_final_portfolio, export_portfolio
from backtest.engine import run_scenario_backtest

def main():
    # 1. Load Data
    prices = load_from_cache("data/cache/universe_prices.csv")
    
    # 2. Generate Signals & Macro Logic
    q_views, initial_omega, kill_switch = compose_bl_inputs(prices)
    
    # 3. Factor Analysis for Omega Refinement
    idio_risk = calculate_idiosyncratic_risk(prices.pct_change())
    
    # 4. Optimization Sequence
    hrp_prior = get_hrp_prior_weights(prices.pct_change())
    bl_port = construct_bl_model(prices.pct_change(), hrp_prior, q_views, idio_risk)
    
    # 5. Constraints & Selection
    final_top_10 = select_final_portfolio(bl_port.w, liquidity_caps={}) # Caps can be passed here
    export_portfolio(final_top_10, "outputs/final_weights.csv")
    
    # 6. Backtest 2026 Scenario
    mideast_bt = run_scenario_backtest(prices, final_top_10, "MIDEAST_2026")
    print(mideast_bt.stats())

if __name__ == "__main__":
    main()