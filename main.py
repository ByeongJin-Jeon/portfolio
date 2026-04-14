# -*- coding: utf-8 -*-
"""
main.py (Final Stage 4)
======================
The Grand Finale: Executes Filtering, Optimization, and Resilience Backtesting.
"""

import os
import shutil

os.environ['NUMBA_DISABLE_CACHE'] = '1'
os.environ['NUMBA_CACHE_DIR'] = '/tmp/numba_cache_fresh'

import time
import pandas as pd
import yfinance as yf
from config import (
    BACKTEST_INITIAL_CAPITAL, DATA_DIR,
    PRICE_START, PRICE_END
)
from data.universe import UniverseManager
from data.loader import (
    load_from_cache, save_to_cache,
    fetch_data_in_chunks, filter_candidates, apply_currency_conversion
)
from signals.composer import compose_bl_inputs
from portfolio.factor_loading import calculate_idiosyncratic_risk
from optimization.hrp import get_hrp_prior_weights
from optimization.black_litterman import construct_bl_model
from portfolio.selector import select_final_portfolio, export_portfolio
from portfolio.constraints import calculate_liquidity_caps
from backtest.engine import ResilientBacktester, run_scenario_backtest
from evaluation.metrics import calculate_resilience_suite

def main():
    um = UniverseManager()
    full_ticker_list = um.get_full_universe()
    print(f"🛰️ Scanned {len(full_ticker_list)} potential candidates globally.")

    price_path = os.path.join(DATA_DIR, "universe_prices.csv")
    volume_path = os.path.join(DATA_DIR, "universe_volumes.csv")

    print("📥 Fetching fresh data for the entire universe... (This may take a while)")
    full_prices, full_volumes = fetch_data_in_chunks(full_ticker_list, PRICE_START, PRICE_END, chunk_size=50)
    save_to_cache(full_prices, price_path)
    save_to_cache(full_volumes, volume_path)

    raw_prices = load_from_cache(price_path)
    raw_volumes = load_from_cache(volume_path)
    
    print("💱 Converting full universe to KRW for fair comparison...")
    all_prices_krw, _ = apply_currency_conversion(raw_prices)

    candidate_tickers = filter_candidates(all_prices_krw, raw_volumes)
    filtered_prices = all_prices_krw[candidate_tickers]
    filtered_volumes = raw_volumes[candidate_tickers]
    print(f"✅ Filtered down to top {len(candidate_tickers)} momentum leaders.")
    
    returns = filtered_prices.ffill().pct_change(fill_method=None).dropna()
    # returns = returns.clip(lower=-0.3, upper=0.3) 
    # print("⚠️ Corrected outliers (±30%).")

    q_views, initial_omega, kill_switch_active = compose_bl_inputs(filtered_prices)

    idio_risk = calculate_idiosyncratic_risk(returns)
    hrp_prior = get_hrp_prior_weights(returns)
    bl_port = construct_bl_model(returns, hrp_prior, q_views, idio_risk)

    liquidity_caps = calculate_liquidity_caps(filtered_volumes, filtered_prices, BACKTEST_INITIAL_CAPITAL)
    final_weights = select_final_portfolio(bl_port, liquidity_caps)
    
    export_portfolio(final_weights, "outputs/final_weights.csv")

    print("\n📊 Running 'MIDEAST_2026' Resilience Simulation...")
    backtester = ResilientBacktester(all_prices_krw)
    
    all_results = backtester.run_all_scenarios(final_weights)

    print("\n" + "="*60)
    print("🏆 FINAL MULTI-SCENARIO RESILIENCE REPORT 🏆")
    print("="*60)
    
    for scenario_name, pf_result in all_results.items():
        if pf_result is None:
            print(f"\n[Scenario: {scenario_name}] - No data available, skipping report.")
            continue
        stats = calculate_resilience_suite(pf_result)
        
        print(f"\n[Scenario: {scenario_name}]")
        print("-" * 30)
        for metric, value in stats.items():
            print(f" - {metric:25}: {value:10.2f}")

    print("\n" + "="*50)
    print("🏆 BACKTEST SCORECARD 🏆")
    print("="*50)
    for metric, value in stats.items():
        print(f"{metric}: {value:.2f}")
    
    print("\n✅ Strategy execution complete. Check 'outputs/' for details.")

if __name__ == "__main__":
    main()