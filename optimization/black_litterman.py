# -*- coding: utf-8 -*-
"""
optimization/black_litterman.py
================================
Optional Black-Litterman module.

NOT in the default production pipeline.
Only used when ENABLE_BLACK_LITTERMAN = True is set explicitly in config.

If enabled, BL adjusts the mu_tilde vector with posterior views
before passing to the mean-risk optimizer.  Views must be provided
externally (e.g., analyst overrides) via the views dict.

This module does NOT:
  - generate directional alpha from trend signals
  - override the IC-scaled fundamental mu
  - replace the QP optimizer
"""

import numpy as np
import pandas as pd


def construct_bl_posterior(
    mu_prior: pd.Series,
    Sigma: pd.DataFrame,
    views: dict,
    tau: float = 0.05,
    risk_aversion: float = 2.5,
) -> pd.Series:
    """
    Computes the Black-Litterman posterior expected return.

    Parameters
    ----------
    mu_prior     : IC-scaled prior expected return vector
    Sigma        : (n x n) covariance matrix
    views        : dict of {ticker: annualized_return_view}  (absolute views)
    tau          : uncertainty scaling on the prior (BL_TAU)
    risk_aversion: used only to re-scale the equilibrium Pi

    Returns
    -------
    mu_bl : posterior expected return vector
    """
    tickers = mu_prior.index.tolist()
    n       = len(tickers)
    mu_arr  = mu_prior.values.astype(float).reshape(-1, 1)
    S       = Sigma.reindex(tickers, columns=tickers).fillna(0).values.astype(float)

    active   = {k: v for k, v in views.items() if k in tickers}
    if not active:
        return mu_prior.copy()

    k        = len(active)
    asset_idx = {t: i for i, t in enumerate(tickers)}

    P = np.zeros((k, n))
    Q = np.zeros((k, 1))
    for row, (ticker, view) in enumerate(active.items()):
        P[row, asset_idx[ticker]] = 1.0
        Q[row, 0] = float(view)

    # Omega: diagonal uncertainty matrix proportional to P Sigma P'
    Omega = np.diag(np.diag(tau * P @ S @ P.T))
    Omega += np.eye(k) * 1e-8

    # BL formula
    tau_S_inv = np.linalg.inv(tau * S + np.eye(n) * 1e-8)
    Omega_inv = np.linalg.inv(Omega)

    M      = np.linalg.inv(tau_S_inv + P.T @ Omega_inv @ P)
    mu_bl  = M @ (tau_S_inv @ mu_arr + P.T @ Omega_inv @ Q)

    return pd.Series(mu_bl.flatten(), index=tickers, name="mu_bl")


def apply_bl_if_enabled(
    mu_tilde: pd.Series,
    Sigma: pd.DataFrame,
    views: dict,
    enabled: bool = False,
    tau: float = 0.05,
) -> pd.Series:
    """
    Entry point: apply BL only when enabled=True.
    Otherwise returns mu_tilde unchanged.

    views = {} is fine (no-op even when enabled).
    """
    if not enabled or not views:
        return mu_tilde

    return construct_bl_posterior(mu_tilde, Sigma, views, tau)
