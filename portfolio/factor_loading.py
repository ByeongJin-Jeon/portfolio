# -*- coding: utf-8 -*-
import pandas as pd
import statsmodels.api as sm
from pandas_datareader.famafrench import get_available_datasets
import pandas_datareader.data as web
from config import FF_LIBRARY, FF_REGRESSION_WINDOW, RISK_FREE_RATE

def fetch_ff_factors():
    """Fetches the latest daily 5-factor data from the French library."""
    ds = web.DataReader(FF_LIBRARY, 'famafrench', start='2020-01-01')[0]
    return ds / 100.0

def calculate_idiosyncratic_risk(asset_returns):
    """
    Runs FF5 regressions to extract residuals (Idiosyncratic Variance).
    Higher residual variance = Higher uncertainty (larger Omega entry).
    """
    ff_factors = fetch_ff_factors()
    
    data = pd.concat([asset_returns, ff_factors], axis=1).dropna()
    
    idiosyncratic_vars = {}
    
    # Factor column names in the 2x3 daily dataset
    factors = ['Mkt-RF', 'SMB', 'HML', 'RMW', 'CMA']
    X = sm.add_constant(data[factors])
    
    for asset in asset_returns.columns:
        y = data[asset] - data['RF']
        
        # Rolling regression or full-window regression
        model = sm.OLS(y, X).fit()
        
        # The variance of the residuals is our measure of 'Uncertainty'
        idiosyncratic_vars[asset] = model.resid.var()
        
    return pd.Series(idiosyncratic_vars)

def extract_idiosyncratic_alpha(asset_returns, ff_factors):
    """
    Extracts 'Inherent Ascent Power (Alpha)' that is not explained by the FF5 factor.
    """  
    data = pd.concat([asset_returns, ff_factors], axis=1).dropna()
    factors = ['Mkt-RF', 'SMB', 'HML', 'RMW', 'CMA']
    X = sm.add_constant(data[factors])
    
    alpha_views = pd.Series(0.0, index=asset_returns.columns)
    
    for asset in asset_returns.columns:
        y = data[asset] - data['RF']
        model = sm.OLS(y, X).fit()
        
        # Confirmation of residual momentum over the past 20 days
        recent_residuals = model.resid.tail(20)
        
        if recent_residuals.empty:
            continue
            
        # Calculate how 'extreme' this alpha is (Z-Score of the residual)
        if recent_residuals.mean() > 0 and recent_residuals.iloc[-1] > 0:
            z_score = recent_residuals.mean() / (recent_residuals.std() + 1e-6)
            
            # Dynamic Scaling: 1 Z-score = +5% alpha, capped at an extreme +20%
            dynamic_alpha = min(0.20, z_score * 0.05)
            alpha_views[asset] = dynamic_alpha
            
        elif recent_residuals.mean() < 0 and recent_residuals.iloc[-1] < 0:
            z_score = abs(recent_residuals.mean() / (recent_residuals.std() + 1e-6))
            # Bad news is capped at -10% extra penalty
            dynamic_alpha = max(-0.10, -1.0 * z_score * 0.05)
            alpha_views[asset] = dynamic_alpha
            
    return alpha_views