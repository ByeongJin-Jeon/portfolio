# -*- coding: utf-8 -*-
"""
optimization/hrp.py
===================
HRP benchmark / fallback optimizer.

Role in the new architecture:
  - PRIMARY: Not the production optimizer. Use optimization/mean_risk.py for that.
  - FALLBACK: Called when the cvxpy QP fails to converge.
  - BENCHMARK: Used for risk attribution comparison only.

HRP does not require an expected return vector (mu), which makes it
a useful robustness check independent of the alpha model.
"""

import numpy as np
import pandas as pd
import riskfolio as rp
from config import HRP_LINKAGE_METHOD, HRP_DISTANCE_METRIC


def get_hrp_weights(returns: pd.DataFrame) -> pd.Series:
    """
    Computes HRP (Hierarchical Risk Parity) weights as a benchmark/fallback.

    Does NOT require a mu vector — uses empirical covariance only.
    Returns equal-weight allocation if HRP fails.
    """
    tickers = returns.columns.tolist()
    n = len(tickers)
    default = pd.Series(1.0 / n, index=tickers)

    try:
        port = rp.HCPortfolio(returns=returns)
        hrp_df = port.optimization(
            model="HRP",
            codependence=HRP_DISTANCE_METRIC,
            linkage=HRP_LINKAGE_METHOD,
            rm="MV",
            rf=0,
        )
        if hrp_df is None or hrp_df.empty:
            return default
        w = hrp_df.iloc[:, 0]
        w = w.reindex(tickers).fillna(0.0)
        total = w.sum()
        if total > 1e-8:
            return (w / total).rename("hrp_weights")
        return default
    except Exception:
        return default
