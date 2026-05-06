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
    PRICE_START, PRICE_END, USE_CACHE_DATA,
    BACKTEST_ENABLE
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
from backtest.engine import ResilientBacktester
from evaluation.metrics import calculate_resilience_suite

def main():
    um = UniverseManager()
    full_ticker_list = um.get_full_universe()
    print(f"🛰️ Scanned {len(full_ticker_list)} potential candidates globally.")

    price_path = os.path.join(DATA_DIR, "universe_prices.csv")
    volume_path = os.path.join(DATA_DIR, "universe_volumes.csv")

    if USE_CACHE_DATA and os.path.exists(price_path) and os.path.exists(volume_path):
        print("📦 USE_CACHE_DATA is True. Loading data from local cache...")
        all_prices_raw = load_from_cache(price_path)
        all_volumes = load_from_cache(volume_path)
    else:
        print(f"📥 Fetching fresh data for the entire universe... (This may take a while)")
        all_prices_raw, all_volumes = fetch_data_in_chunks(
            full_ticker_list, 
            start_date=PRICE_START, 
            end_date=PRICE_END
        )
        save_to_cache(all_prices_raw, price_path)
        save_to_cache(all_volumes, volume_path)
    
    print("💱 Converting full universe to KRW for fair comparison...")
    try:
        conversion_result = apply_currency_conversion(all_prices_raw)
        if isinstance(conversion_result, tuple):
            all_prices_krw = conversion_result[0]
        else:
            all_prices_krw = conversion_result
    except Exception as e:
        print(f"⚠️ Currency conversion failed: {e}. Using raw prices.")
        all_prices_krw = all_prices_raw
    
    def my_quant_strategy(past_prices):
        """
        The Brain of our Walk-Forward Time Machine.
        Takes ONLY past data, outputs optimal weights. No future peeking!
        """
        # Data sufficiency check (Need at least 1 year of data for FF5 & Volatility)
        if len(past_prices) < 252:
            return pd.Series(0.0, index=past_prices.columns)
        
        past_volumes_all = all_volumes.loc[past_prices.index]
        past_candidates = filter_candidates(past_prices, past_volumes_all)

        recent_prices = past_prices[past_candidates].tail(252).ffill()
        recent_volumes = past_volumes_all[past_candidates].tail(252).ffill()

        valid_tickers = recent_prices.columns[recent_prices.notna().all()]
        valid_prices = recent_prices[valid_tickers]
        valid_volumes = recent_volumes[valid_tickers]

        if len(valid_tickers) < 10:
            return pd.Series(0.0, index=past_prices.columns)

        # 1. Calculate Returns
        returns = valid_prices.pct_change(fill_method=None).dropna()

        # 2. Generate Signals (Macro, Trend, Fundamental, Skew)
        try:
            # Note: compose_bl_inputs might print lots of logs. 
            # In a real backtest, you might want to suppress these prints to keep the terminal clean.
            q_views, initial_omega, kill_switch_active = compose_bl_inputs(valid_prices, valid_volumes)
        except Exception as e:
            print(f"      -> [ERROR] Signal generation failed: {e}")
            return pd.Series(0.0, index=past_prices.columns)

        # 3. Factor Loading & Idiosyncratic Risk
        idio_risk = calculate_idiosyncratic_risk(returns)

        # 4. HRP Prior
        hrp_prior = get_hrp_prior_weights(returns)

        # 5. Black-Litterman Optimization
        bl_port = construct_bl_model(returns, hrp_prior, q_views, idio_risk)

        # 6. Liquidity Constraints (Align volumes with the past timeframe!)
        liquidity_caps = calculate_liquidity_caps(valid_volumes, valid_prices, BACKTEST_INITIAL_CAPITAL)

        # 7. Final Selection
        final_w = select_final_portfolio(bl_port, liquidity_caps)
        
        return final_w.reindex(past_prices.columns).fillna(0.0)

    # --- CURRENT LIVE VIEW ---
    print("\n🔮 [CURRENT LIVE VIEW] Generating Today's Optimal Portfolio...")
    current_live_weights = my_quant_strategy(all_prices_krw)
    export_portfolio(current_live_weights, "outputs/final_weights.csv")

    # Save OHLCV data for final tickers
    final_tickers = current_live_weights[current_live_weights > 0].index.tolist()
    ohlcv_dir = "outputs/ohlcv"
    
    if os.path.exists(ohlcv_dir):
        shutil.rmtree(ohlcv_dir)
    os.makedirs(ohlcv_dir, exist_ok=True)
    
    if final_tickers:
        print(f"📥 Saving OHLCV data for {len(final_tickers)} tickers to {ohlcv_dir}...")
        for ticker in final_tickers:
            yf_ticker = ticker
            if str(ticker)[0].isdigit():
                yf_ticker = f"{ticker.split('-')[0]}.KS"
            
            try:
                data = yf.download(yf_ticker, start=PRICE_START, end=PRICE_END, auto_adjust=True, progress=False)
                if not data.empty:
                    data.to_csv(os.path.join(ohlcv_dir, f"{ticker}.csv"))
            except Exception as e:
                print(f"      ⚠️ Failed to download OHLCV for {ticker}: {e}")

    if not BACKTEST_ENABLE:
        exit()
    # --- WALK-FORWARD BACKTESTING ---
    print("\n📊 [BACKTEST] Running Walk-Forward Resilience Simulation...")
    backtester = ResilientBacktester(all_prices_krw, strategy_func=my_quant_strategy)
    all_results = backtester.run_all_scenarios()

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

if __name__ == "__main__":
    main()