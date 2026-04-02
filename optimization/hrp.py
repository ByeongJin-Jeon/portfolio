# -*- coding: utf-8 -*-
import riskfolio as rp
from config import SEGMENT_MAP, HRP_LINKAGE_METHOD, HRP_DISTANCE_METRIC

def get_hrp_prior_weights(returns):
    """
    Calculates the 'Equilibrium' weights using HRP.
    This acts as the 'Prior' for our Black-Litterman model.
    """
    # Initialize the Portfolio object
    port = rp.Portfolio(returns=returns)
    
    # Calculate Codependence and Linkage
    # We use Pearson correlation and Ward linkage to find stable clusters
    port.assets_stats(method_mu='hist', method_cov='hist', d=0.94)
    
    # Optimization: HRP doesn't require a mean vector (mu), making it robust
    # to the 'noise' of 2026 geopolitical shifts.
    hrp_weights = port.optimization(
        model='HRP',
        codependence=HRP_DISTANCE_METRIC,
        linkage=HRP_LINKAGE_METHOD,
        rm='MV',  # Standard variance as the risk measure for HRP
        rf=0,
        hist=True
    )
    
    return hrp_weights