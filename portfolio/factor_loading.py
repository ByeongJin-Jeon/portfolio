# -*- coding: utf-8 -*-
import pandas as pd
import statsmodels.api as sm
from pandas_datareader.famafrench import get_available_datasets
import pandas_datareader.data as web
from config import FF_LIBRARY, FF_REGRESSION_WINDOW, RISK_FREE_RATE, PRICE_START

def fetch_ff_factors():
    """Fetches the latest daily 5-factor data from the French library."""
    # Use PRICE_START from config to ensure enough history for backtesting
    ds = web.DataReader(FF_LIBRARY, 'famafrench', start=PRICE_START)[0]

    if isinstance(ds.index, pd.PeriodIndex):
        ds.index = ds.index.to_timestamp()

    return ds / 100.0

def calculate_idiosyncratic_risk(asset_returns):
    """
    Runs FF5 regressions to extract residuals (Idiosyncratic Variance).
    Higher residual variance = Higher uncertainty (larger Omega entry).
    """
    ff_factors = fetch_ff_factors()   
    idiosyncratic_vars = {}
    
    # Factor column names in the 2x3 daily dataset
    factors = ['Mkt-RF', 'SMB', 'HML', 'RMW', 'CMA']

    for asset in asset_returns.columns:
        data = pd.concat([asset_returns[asset], ff_factors], axis=1).dropna()
        
        if len(data) < 30:
            idiosyncratic_vars[asset] = 0.1
            continue
            
        X = sm.add_constant(data[factors])
        y = data[asset] - data['RF']
        
        try:
            model = sm.OLS(y, X).fit()
            idiosyncratic_vars[asset] = model.resid.var()
        except:
            idiosyncratic_vars[asset] = 0.1
            
    return pd.Series(idiosyncratic_vars)

def extract_idiosyncratic_alpha(asset_returns, ff_factors):
    """
    Extracts 'Inherent Ascent Power (Alpha)' that is not explained by the FF5 factor.
    """
    factors = ['Mkt-RF', 'SMB', 'HML', 'RMW', 'CMA']    
    alpha_views = pd.Series(0.0, index=asset_returns.columns)
    
    for asset in asset_returns.columns:
        data = pd.concat([asset_returns[asset], ff_factors], axis=1).dropna()
        
        if len(data) < 30:
            continue

        X = sm.add_constant(data[factors])
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