# -*- coding: utf-8 -*-
"""
main.py — 16-step institutional pipeline
=========================================
Implements the QUANT_REDESIGN_PLAN_v2 architecture.

Step  1  Load config + environment
Step  2  Universe metadata
Step  3  Fetch / cache price + volume data
Step  4  Build candidate frame (eligibility filter — no trend)
Step  5  Apply currency conversion
Step  6  Macro risk governor → constraint adjustments
Step  7  Build factor risk model (EWMA + Ledoit-Wolf + Gram-Schmidt)
Step  8  Build fundamental alpha (IC-scaled equity mu, ETF mu=0)
Step  9  Build uncertainty + liquidity penalties
Step 10  Assemble mu_tilde = mu - gamma_u * u - gamma_l * l
Step 11  (Optional) Black-Litterman posterior adjustment
Step 12  Compute liquidity participation-rate caps
Step 13  Solve constrained QP (cvxpy) with CVaR/CDaR overlay
Step 14  Validate weights + build exposure/risk/alpha reports
Step 15  Generate execution order plan
Step 16  (Optional) Walk-forward backtest
"""

import os
import sys
import shutil
import warnings
import pandas as pd
import numpy as np
import yfinance as yf

os.environ["NUMBA_DISABLE_CACHE"] = "1"
warnings.filterwarnings("ignore")

from config import (
    BACKTEST_INITIAL_CAPITAL, DATA_DIR, OUTPUT_DIR,
    PRICE_START, PRICE_END, USE_CACHE_DATA, BACKTEST_ENABLE,
    COVARIANCE_WINDOW, CVAR_LIMIT, CDAR_LIMIT, CVAR_ALPHA,
    OPTIMIZER_RISK_AVERSION, OPTIMIZER_HOLDING_REG,
    SNAPSHOT_DIR, ENABLE_BLACK_LITTERMAN,
)
from data.universe import UniverseManager
from data.loader import (
    load_from_cache, save_to_cache,
    fetch_data_in_chunks, build_candidate_frame,
    apply_basic_eligibility, apply_currency_conversion,
    compute_adv,
)
from signals.composer import assemble_net_expected_return, get_constraint_adjustments
from signals.fundamental import build_fundamental_snapshot_table
from portfolio.factor_loading import build_risk_model
from portfolio.constraints import build_all_constraints, compute_liquidity_caps
from portfolio.selector import (
    validate_portfolio, build_exposure_report,
    build_risk_report, build_alpha_report, export_portfolio,
)
from portfolio.execution import generate_order_plan, fetch_current_prices
from optimization.mean_risk import solve_mean_risk
from optimization.hrp import get_hrp_weights
from optimization.black_litterman import apply_bl_if_enabled
from backtest.engine import SnapshotWalkForward, HistoricalRiskReplay
from evaluation.metrics import calculate_resilience_suite, compute_portfolio_returns_from_vbt


def _ensure_dirs():
    os.makedirs(DATA_DIR,   exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)


def main():
    _ensure_dirs()
    nav = float(BACKTEST_INITIAL_CAPITAL)

    # ── Step 1  Load config --------------------------------------------------
    print("[1/16] Configuration loaded.")

    # ── Step 2  Universe metadata -------------------------------------------
    print("[2/16] Building universe metadata...")
    um           = UniverseManager()
    metadata_df  = um.get_universe_metadata()
    full_tickers = metadata_df.index.tolist()
    print(f"       {len(full_tickers)} assets in universe "
          f"({(metadata_df['is_etf_shelter']).sum()} ETF shelters).")

    # ── Step 3  Fetch / cache data ------------------------------------------
    print("[3/16] Fetching price and volume data...")
    price_path  = os.path.join(DATA_DIR, "universe_prices.csv")
    volume_path = os.path.join(DATA_DIR, "universe_volumes.csv")

    if USE_CACHE_DATA and os.path.exists(price_path) and os.path.exists(volume_path):
        print("       Using cached data.")
        all_prices  = load_from_cache(price_path)
        all_volumes = load_from_cache(volume_path)
    else:
        all_df_dict = fetch_data_in_chunks(
            full_tickers, start_date=PRICE_START, end_date=PRICE_END,
        )
        all_prices = all_df_dict.get("close")
        all_volumes = all_df_dict.get("volume")
        save_to_cache(all_prices, price_path)
        save_to_cache(all_volumes, volume_path)
    print(f"       Prices: {all_prices.shape}, Volumes: {all_volumes.shape}")

    # ── Step 4  Candidate frame (eligibility) --------------------------------
    print("[4/16] Building candidate frame...")
    candidate_df = build_candidate_frame(all_prices, all_volumes, metadata_df)
    candidate_df = apply_basic_eligibility(candidate_df)
    tickers      = candidate_df.index.tolist()
    print(f"       {len(tickers)} eligible assets "
          f"({candidate_df['is_etf_shelter'].sum()} ETF shelters).")

    # ── Step 5  Currency conversion -----------------------------------------
    print("[5/16] Applying currency conversion...")
    try:
        prices_base, fx_rates = apply_currency_conversion(
            all_prices[tickers], metadata_df.reindex(tickers)
        )
    except Exception as e:
        print(f"       Currency conversion failed ({e}); using raw prices.")
        prices_base = all_prices[tickers]
        fx_rates    = None

    # ── Step 6  Macro risk governor -----------------------------------------
    print("[6/16] Fetching macro state and adjusting constraints...")
    constraint_adj = get_constraint_adjustments(is_live=True)
    macro_state    = constraint_adj["macro_state"]
    sleeve_bounds  = constraint_adj["sleeve_bounds"]
    ccy_bounds     = constraint_adj["ccy_bounds"]
    print(f"       Stress regime: {macro_state['stress_regime']}  "
          f"VIX={macro_state['vix_level']:.1f}")

    # ── Step 7  Factor risk model --------------------------------------------
    print("[7/16] Building factor risk model (EWMA + LW + Gram-Schmidt)...")
    recent_returns = (
        prices_base.tail(COVARIANCE_WINDOW)
        .pct_change(fill_method=None)
        .dropna(how="all")
        .fillna(0.0)
    )
    Sigma, sigma_spec, B_orth, F = build_risk_model(
        recent_returns, metadata_df.reindex(tickers)
    )
    print(f"       Sigma: {Sigma.shape}, factors: {B_orth.shape[1]}")

    # ── Step 8  Fundamental alpha -------------------------------------------
    print("[8/16] Computing IC-scaled fundamental alpha (equity only)...")
    snapshot_df = build_fundamental_snapshot_table(tickers)
    print(f"       Snapshot: {len(snapshot_df)} equity assets.")

    # ── Step 9 + 10  Assemble mu_tilde --------------------------------------
    print("[9-10/16] Assembling mu_tilde = mu - gamma_u*u - gamma_l*l ...")
    mu_tilde, mu, u_vec, l_vec = assemble_net_expected_return(
        snapshot_df,
        sigma_spec,
        candidate_df,
        nav=nav,
    )

    # ── Step 11  Optional BL adjustment ------------------------------------
    print("[11/16] Black-Litterman adjustment (enabled={})...".format(ENABLE_BLACK_LITTERMAN))
    bl_views  = {}   # analyst overrides; empty = no adjustment
    mu_final  = apply_bl_if_enabled(mu_tilde, Sigma, bl_views, enabled=ENABLE_BLACK_LITTERMAN)

    # ── Step 12  Liquidity caps ---------------------------------------------
    print("[12/16] Computing liquidity participation-rate caps...")
    liq_caps = compute_liquidity_caps(
        all_volumes.reindex(columns=tickers),
        all_prices.reindex(columns=tickers),
        nav,
    )

    # ── Step 13  Solve QP ---------------------------------------------------
    print("[13/16] Solving constrained mean-risk QP (cvxpy)...")
    w_ref    = pd.Series(1.0 / len(tickers), index=tickers)
    weights, qp_status, qp_meta = solve_mean_risk(
        mu_final,
        Sigma,
        tickers,
        metadata_df.reindex(tickers),
        liq_caps,
        returns_df     = recent_returns,
        w_ref          = w_ref,
        lambda_r       = OPTIMIZER_RISK_AVERSION,
        lambda_h       = OPTIMIZER_HOLDING_REG,
        sleeve_bounds  = sleeve_bounds,
        ccy_bounds     = ccy_bounds,
        apply_cvar     = True,
        apply_cdar     = True,
        cvar_limit     = CVAR_LIMIT,
        cdar_limit     = CDAR_LIMIT,
        cvar_alpha     = CVAR_ALPHA,
    )

    if qp_status not in ("optimal", "optimal_inaccurate"):
        print(f"       QP solver status: {qp_status}. Falling back to HRP.")
        weights = get_hrp_weights(recent_returns)

    print(f"       Solver: {qp_status}  port_vol={qp_meta.get('port_vol', 0):.1%}  "
          f"port_ret={qp_meta.get('port_ret', 0):.1%}")

    # ── Step 14  Validate + report ------------------------------------------
    print("[14/16] Validating weights and building reports...")
    validation = validate_portfolio(weights, metadata_df.reindex(tickers), sigma_spec, Sigma)
    if not validation["valid"]:
        for issue in validation["issues"]:
            print(f"       WARNING: {issue}")

    exposure_report = build_exposure_report(weights, metadata_df.reindex(tickers))
    risk_report     = build_risk_report(weights, Sigma, B_orth, F, sigma_spec)

    composite_z = pd.Series(0.0, index=tickers)  # placeholder if snapshot was empty
    alpha_report = build_alpha_report(weights, mu, mu_final, composite_z, u_vec, l_vec)

    # Save reports
    weights.to_csv(os.path.join(OUTPUT_DIR, "final_weights.csv"))
    alpha_report.to_csv(os.path.join(OUTPUT_DIR, "alpha_report.csv"))
    for dim, series in exposure_report.items():
        series.to_csv(os.path.join(OUTPUT_DIR, f"exposure_{dim}.csv"))

    print("\n--- Portfolio Weights ---")
    active = weights[weights > 1e-4].sort_values(ascending=False)
    for ticker, w_val in active.items():
        mu_val = float(mu_final.get(ticker, 0.0))
        print(f"  {ticker:15s}  {w_val:.2%}   mu_tilde={mu_val:.2%}")

    print("\n--- Exposure ---")
    for dim, series in exposure_report.items():
        top = series.head(5)
        print(f"  {dim}: " + "  ".join(f"{k}={v:.1%}" for k, v in top.items()))

    print(f"\n  Portfolio vol: {risk_report['port_vol_ann']:.1%}  "
          f"Specific share: {risk_report['specific_var_share']:.1%}")

    # ── Step 15  Execution plan ---------------------------------------------
    print("[15/16] Generating execution order plan...")
    current_prices_series = fetch_current_prices(tickers)

    order_df = generate_order_plan(
        weights,
        current_weights = None,
        nav             = nav,
        volume_df       = all_volumes.reindex(columns=tickers),
        price_df        = all_prices.reindex(columns=tickers),
        current_prices  = current_prices_series,
    )
    order_path = os.path.join(OUTPUT_DIR, "execution_plan.csv")
    order_df.to_csv(order_path, encoding="utf-8-sig", index=False)
    print(f"       Order plan saved to {order_path}")
    if not order_df.empty:
        print(order_df.to_string(index=False))

    # ── Step 16  Backtest (optional) ----------------------------------------
    if not BACKTEST_ENABLE:
        print("[16/16] Backtest disabled (BACKTEST_ENABLE=False). Done.")
        return

    print("[16/16] Running historical risk replay backtest...")
    engine = HistoricalRiskReplay(prices_base)
    results = engine.run_all_scenarios_static(weights)

    print("\n=== Multi-Scenario Resilience Report ===")
    for scenario, pf in results.items():
        if pf is None:
            print(f"  [{scenario}] No data.")
            continue
        ret_series = compute_portfolio_returns_from_vbt(pf)
        metrics    = calculate_resilience_suite(ret_series)
        print(f"\n  [{scenario}]")
        for k, v in metrics.items():
            print(f"    {k:30s}: {v:.4f}")


if __name__ == "__main__":
    main()
