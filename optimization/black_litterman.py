# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import riskfolio as rp
from config import BL_TAU, BL_RISK_AVERSION, RISK_FREE_RATE, CDAR_LIMIT, CDAR_ALPHA

def construct_bl_model(returns, hrp_weights, tactical_views, idiosyncratic_vars):
    """
    Integrates tactical views and executes CDaR optimization for UPI maximization.
    """
    # 1. P Matrix (Picking Matrix)
    active_assets = tactical_views[tactical_views != 0].index
    if len(active_assets) == 0: # Fallback if no signals
        return hrp_weights
        
    P = pd.DataFrame(0, index=active_assets, columns=returns.columns)
    for asset in active_assets:
        P.loc[asset, asset] = 1
        
    # 2. Q Vector (Views)
    Q = tactical_views.loc[active_assets].values.reshape(-1, 1)
    
    # 3. Omega (Uncertainty Matrix)
    Omega = np.diag(idiosyncratic_vars.loc[active_assets] * BL_TAU)
    
    # 4. Black-Litterman Setup
    port = rp.Portfolio(returns=returns)
    port.assets_stats(method_mu='hist', method_cov='hist')
    
    port.blacklitterman_stats(
        P=P.values,
        Q=Q,
        rf=RISK_FREE_RATE,
        w=hrp_weights.values.reshape(-1, 1), 
        delta=BL_RISK_AVERSION,
        tau=BL_TAU,
        Omega=Omega
    )
    
    # 5. Optimization: Maximize UPI subject to CDaR <= 15%
    # In Riskfolio, 'Sharpe' + rm='CDaR' maximizes the Ulcer Performance Index

    # Stage 1: Attempt to Maximize UPI (Return/CDaR)
    port.alpha = CDAR_ALPHA
    w_optimized = port.optimization(
        model='BL', 
        rm='CDaR', 
        obj='Sharpe', 
        rf=RISK_FREE_RATE, 
        hist=True
    )
    
    # Calculate the CDaR of the resulting portfolio
    # Riskfolio returns weights as a DataFrame; we pass them to the risk function
    current_cdar = rp.RiskFunctions.CDaR_Hist(w_optimized, returns, alpha=CDAR_ALPHA)

    # Stage 2: Fallback if CDaR exceeds hard limit
    if current_cdar > CDAR_LIMIT:
        print(f"⚠️ CDaR breach detected ({current_cdar:.2%}). Switching to MinRisk objective.")
        w_optimized = port.optimization(
            model='BL',
            rm='CDaR',
            obj='MinRisk', # Force the safest possible allocation
            hist=True
        )
    
    return w_optimized