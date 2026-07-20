# -*- coding: utf-8 -*-
"""
portfolio/factor_loading.py
===========================
Orthogonalized factor risk model with EWMA + Ledoit-Wolf shrinkage.

Architecture:
  build_factor_exposure_matrix      -> B  (n x k)
  orthogonalize_factor_exposures    -> B_orth  (Gram-Schmidt in priority order)
  estimate_factor_covariance        -> F  (k x k, EWMA 252d halflife=63, LW)
  estimate_specific_risk            -> D  diagonal  (n x n)
  build_total_covariance            -> Sigma = B_orth @ F @ B_orth.T + D

Factor priority for Gram-Schmidt: sleeve > country > sector > currency
"""

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf
from config import COVARIANCE_WINDOW, EWMA_HALFLIFE, LEDOIT_WOLF_SHRINKAGE, SPECIFIC_RISK_FLOOR, FACTOR_PRIORITY


# ── factor exposure matrix ────────────────────────────────────────────────────

def build_factor_exposure_matrix(metadata_df: pd.DataFrame) -> pd.DataFrame:
    """
    Builds a one-hot factor exposure matrix B (n x k).
    Columns are indicator variables for each level of: sleeve, country, sector, currency.

    Parameters
    ----------
    metadata_df : index = tickers, columns include sleeve, country, sector, trading_currency

    Returns
    -------
    B : DataFrame (n_assets x n_factors), column names like "sleeve__global_equity",
        "country__US", "sector__Technology", "currency__USD"
    """
    blocks = []
    col_map = {
        "sleeve":            "sleeve",
        "country":           "country",
        "sector":            "sector",
        "currency":          "trading_currency",
    }

    for factor_type in FACTOR_PRIORITY:
        col = col_map.get(factor_type)
        if col not in metadata_df.columns:
            continue
        dummies = pd.get_dummies(metadata_df[col], prefix=f"{factor_type}").astype(float)
        blocks.append(dummies)

    if not blocks:
        return pd.DataFrame(index=metadata_df.index)

    return pd.concat(blocks, axis=1).fillna(0.0)


def orthogonalize_factor_exposures(B: pd.DataFrame) -> pd.DataFrame:
    """
    Gram-Schmidt orthogonalization of the factor exposure matrix B.

    Columns are processed in order (FACTOR_PRIORITY determines block order).
    Within each factor block the first column is the reference; subsequent
    columns have their projection onto all earlier columns removed.

    This eliminates multicollinearity from one-hot blocks where
    sum_j B_ij = 1 for each block (perfect collinearity with constant).

    Returns
    -------
    B_orth : DataFrame same shape as B, orthogonal columns (unit-free scaling)
    """
    if B.empty:
        return B.copy()

    X = B.values.astype(float).copy()
    cols = list(B.columns)
    n_cols = X.shape[1]
    Q = np.zeros_like(X)

    for j in range(n_cols):
        v = X[:, j].copy()
        for k in range(j):
            qk = Q[:, k]
            norm_sq = qk @ qk
            if norm_sq > 1e-12:
                v = v - (v @ qk / norm_sq) * qk
        norm = np.sqrt(v @ v)
        if norm > 1e-10:
            Q[:, j] = v / norm
        else:
            Q[:, j] = 0.0

    return pd.DataFrame(Q, index=B.index, columns=cols)


# ── EWMA covariance with Ledoit-Wolf ─────────────────────────────────────────

def _ewma_weights(n: int, halflife: int) -> np.ndarray:
    """Returns normalized EWMA weights for n observations (oldest first)."""
    lam = np.log(2) / halflife
    w   = np.exp(-lam * np.arange(n - 1, -1, -1))
    return w / w.sum()


def estimate_factor_covariance(
    returns_df: pd.DataFrame,
    B_orth: pd.DataFrame,
) -> pd.DataFrame:
    """
    Estimates the factor covariance matrix F using a 252-day EWMA + Ledoit-Wolf.

    Steps:
      1. Project returns onto orthogonal factor columns:  f_t = B_orth.T @ r_t
      2. Weight factor returns with EWMA (halflife=63d)
      3. Compute weighted sample covariance
      4. Apply Ledoit-Wolf analytical shrinkage

    Returns
    -------
    F : (k x k) factor covariance DataFrame indexed by factor names
    """
    n_obs = min(len(returns_df), COVARIANCE_WINDOW)
    ret   = returns_df.iloc[-n_obs:].values  # (T x n)
    B_arr = B_orth.reindex(returns_df.columns).fillna(0.0).values  # (n x k)

    factor_returns = ret @ B_arr  # (T x k)
    T = factor_returns.shape[0]

    if T < 10:
        k = B_arr.shape[1]
        return pd.DataFrame(np.eye(k) * SPECIFIC_RISK_FLOOR, columns=B_orth.columns, index=B_orth.columns)

    w   = _ewma_weights(T, EWMA_HALFLIFE)
    mu_f = (factor_returns * w[:, None]).sum(axis=0)
    dev  = factor_returns - mu_f
    F_raw = (dev * w[:, None]).T @ dev

    if LEDOIT_WOLF_SHRINKAGE and T > B_arr.shape[1]:
        lw = LedoitWolf(assume_centered=True)
        lw.fit(dev * np.sqrt(w[:, None]))
        F_shrunk = lw.covariance_
    else:
        F_shrunk = F_raw

    F_shrunk = (F_shrunk + F_shrunk.T) / 2.0
    return pd.DataFrame(F_shrunk, index=B_orth.columns, columns=B_orth.columns)


# ── specific (idiosyncratic) risk ─────────────────────────────────────────────

def estimate_specific_risk(
    returns_df: pd.DataFrame,
    B_orth: pd.DataFrame,
    F: pd.DataFrame,
) -> pd.Series:
    """
    Estimates specific risk D_ii for each asset.

    D_ii = max( Var(r_i) - (B_orth_i @ F @ B_orth_i), SPECIFIC_RISK_FLOOR )
    where Var(r_i) is EWMA-weighted total variance.

    Returns annualized specific risk sqrt(D_ii) in decimal units.
    """
    n_obs   = min(len(returns_df), COVARIANCE_WINDOW)
    ret     = returns_df.iloc[-n_obs:].values  # (T x n)
    T       = ret.shape[0]
    w       = _ewma_weights(T, EWMA_HALFLIFE)

    total_var = ((ret - (ret * w[:, None]).sum(axis=0)) ** 2 * w[:, None]).sum(axis=0)
    total_var *= 252  # annualize

    B_arr  = B_orth.reindex(returns_df.columns).fillna(0.0).values
    F_arr  = F.values
    factor_var = np.diag(B_arr @ F_arr @ B_arr.T) * 252

    spec_var   = np.maximum(total_var - factor_var, SPECIFIC_RISK_FLOOR)
    sigma_spec = np.sqrt(spec_var)

    return pd.Series(sigma_spec, index=returns_df.columns, name="sigma_spec")


# ── total covariance ──────────────────────────────────────────────────────────

def build_total_covariance(
    returns_df: pd.DataFrame,
    B_orth: pd.DataFrame,
    F: pd.DataFrame,
    annualize: bool = True,
) -> pd.DataFrame:
    """
    Builds the full N x N covariance matrix:
      Sigma = B_orth @ F @ B_orth.T + D

    where D = diag(specific_var).

    Returns annualized Sigma (in decimal return units squared).
    """
    tickers = returns_df.columns.tolist()
    B_arr   = B_orth.reindex(tickers).fillna(0.0).values
    F_arr   = F.values

    factor_cov = B_arr @ F_arr @ B_arr.T

    n_obs  = min(len(returns_df), COVARIANCE_WINDOW)
    ret    = returns_df.iloc[-n_obs:].values
    T      = ret.shape[0]
    w      = _ewma_weights(T, EWMA_HALFLIFE)
    total_var = ((ret - (ret * w[:, None]).sum(axis=0)) ** 2 * w[:, None]).sum(axis=0)
    total_var_ann = total_var * 252 if annualize else total_var

    factor_var_ann = np.diag(factor_cov) * (252 if annualize else 1)
    spec_var       = np.maximum(total_var_ann - factor_var_ann, SPECIFIC_RISK_FLOOR)

    factor_cov_ann = factor_cov * (252 if annualize else 1)
    Sigma = factor_cov_ann + np.diag(spec_var)

    Sigma = (Sigma + Sigma.T) / 2.0  # ensure symmetry
    Sigma += np.eye(len(tickers)) * 1e-8  # numerical stability

    return pd.DataFrame(Sigma, index=tickers, columns=tickers)


# ── full pipeline ─────────────────────────────────────────────────────────────

def build_risk_model(
    returns_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.DataFrame]:
    """
    Full factor risk model pipeline.

    Returns
    -------
    Sigma     : (n x n) total covariance matrix (annualized)
    sigma_spec: (n,)    specific risk per ticker (annualized, sqrt of D_ii)
    B_orth    : (n x k) orthogonalized factor exposure matrix
    F         : (k x k) factor covariance matrix (annualized)
    """
    B      = build_factor_exposure_matrix(metadata_df)
    B_orth = orthogonalize_factor_exposures(B)
    F      = estimate_factor_covariance(returns_df, B_orth)
    sigma_spec = estimate_specific_risk(returns_df, B_orth, F)
    Sigma  = build_total_covariance(returns_df, B_orth, F, annualize=True)

    return Sigma, sigma_spec, B_orth, F
