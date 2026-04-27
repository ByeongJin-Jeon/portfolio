# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import riskfolio as rp
from config import BL_TAU, BL_RISK_AVERSION, RM_METHOD, RISK_FREE_RATE, CDAR_LIMIT, CDAR_ALPHA

def construct_bl_model(returns, hrp_weights, tactical_views, idiosyncratic_vars):
    """
    Integrates tactical views and executes CDaR optimization for UPI maximization.
    """
    # 1. P Matrix (Picking Matrix)
    if isinstance(tactical_views, pd.DataFrame):
        tactical_views = tactical_views.iloc[-1]
    
    active_assets = tactical_views[tactical_views != 0].index

    if len(active_assets) == 0: # Fallback if no signals
        return hrp_weights
        
    P = pd.DataFrame(0.0, index=active_assets, columns=returns.columns)
    for asset in active_assets:
        P.loc[asset, asset] = 1.0
        
    # 2. Q Vector (Views)
    # Q = (tactical_views.loc[active_assets].values).reshape(-1, 1)
    Q = (tactical_views.loc[active_assets].values / 252).reshape(-1, 1)
    
    # 3. Omega (Uncertainty Matrix)
    Omega = np.diag(idiosyncratic_vars.loc[active_assets] * BL_TAU)
    
    # 4. Black-Litterman Setup
    port = rp.Portfolio(returns=returns)
    port.assets_stats(method_mu='hist', method_cov='ledoit')

    port.blacklitterman_stats(
        P=P.values,
        Q=Q,
        rf=RISK_FREE_RATE,
        w=hrp_weights.values.reshape(-1, 1), 
        delta=BL_RISK_AVERSION,
    )

    port.cov_bl = port.cov_bl + pd.DataFrame(
        np.eye(port.cov_bl.shape[0]) * 1e-6, 
        index=port.cov_bl.index, 
        columns=port.cov_bl.columns
    )
    
    # 5. Optimization: Maximize UPI subject to CDaR <= 15%
    # In Riskfolio, 'Sharpe' + rm='CDaR' maximizes the Ulcer Performance Index

    # Stage 1: Attempt to Maximize UPI (Return/CDaR)
    port.alpha = CDAR_ALPHA
    # port.upperCDaR = CDAR_LIMIT
    port.upperlng = 0.15

    w_optimized = port.optimization(
        model='BL', 
        rm=RM_METHOD, 
        obj='Sharpe',
        rf=RISK_FREE_RATE,
        hist=True
    )
    
    # If the solver fails to find a solution satisfying both max Sharpe and the CDaR limit:
    if w_optimized is None or w_optimized.empty:
        print("[FALLBACK] Survival comes first! Removing CDaR limit and switching to MinRisk objective.")
        
        port.upperCDaR = None # Remove the strict CDaR limit to give the solver breathing room
        
        w_optimized = port.optimization(
            model='BL',
            rm='CDaR',
            obj='MinRisk',    # Go all-in on defense (Minimize Risk)
            rf=0,
            hist=True
        )
        
        # If it still fails, deploy the last resort: HRP weights
        if w_optimized is None or w_optimized.empty:
             print("[CRITICAL] 2nd optimization failed! Deploying HRP weights as the last resort.")
             w_optimized = hrp_weights
    else:
        print(f"[SUCCESS] Optimization completed!")
    
    return w_optimized