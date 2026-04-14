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