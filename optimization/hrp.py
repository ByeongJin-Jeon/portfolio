# -*- coding: utf-8 -*-
import riskfolio as rp
from config import SEGMENT_MAP, HRP_LINKAGE_METHOD, HRP_DISTANCE_METRIC

def get_hrp_prior_weights(returns):
    """
    Calculates the 'Equilibrium' weights using HRP.
    This acts as the 'Prior' for our Black-Litterman model.
    """
    # Initialize the Portfolio object
    port = rp.HCPortfolio(returns=returns)
    
    # Optimization: HRP doesn't require a mean vector (mu), making it robust
    # to the 'noise' of 2026 geopolitical shifts.
    hrp_weights = port.optimization(
        model='HRP',
        codependence=HRP_DISTANCE_METRIC,
        linkage=HRP_LINKAGE_METHOD,
        rm='MV',  # Standard variance as the risk measure for HRP
        rf=0
    )
    
    return hrp_weights