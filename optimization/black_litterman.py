# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import riskfolio as rp
from config import BL_TAU, BL_RISK_AVERSION

def construct_bl_model(returns, hrp_weights, tactical_views, idiosyncratic_vars):
    """
    Integrates tactical views (Q) and uncertainty (Omega).
    """
    # 1. P Matrix (Picking Matrix): Identify which assets have active views
    active_assets = tactical_views[tactical_views != 0].index
    P = pd.DataFrame(0, index=active_assets, columns=returns.columns)
    for asset in active_assets:
        P.loc[asset, asset] = 1
        
    # 2. Q Vector (Views): The signal strength from trend.py
    Q = tactical_views.loc[active_assets]
    
    # 3. Omega (Uncertainty Matrix)
    # We scale the idiosyncratic variance by Tau and our VIX-based scalar
    # This prevents the portfolio from over-allocating to 'noisy' stock signals.
    Omega = np.diag(idiosyncratic_vars.loc[active_assets] * BL_TAU)
    
    # 4. Black-Litterman Portfolio Object
    port = rp.Portfolio(returns=returns)
    port.assets_stats(method_mu='hist', method_cov='hist')
    
    # Compute BL Adjusted Stats
    port.blacklitterman_stats(
        P=P.values,
        Q=Q.values.reshape(-1, 1),
        rf=RISK_FREE_RATE,
        w=hrp_weights, # Prior weights from HRP
        delta=BL_RISK_AVERSION,
        tau=BL_TAU,
        Omega=Omega
    )
    
    return port