# -*- coding: utf-8 -*-
"""
evaluation/metrics.py
=====================
Performance and risk metrics.

Loss convention for CVaR/CDaR (consistent with Riskfolio-Lib and optimizer):
  CVaR_alpha(w) = -(1/(T*(1-alpha))) * sum of T*(1-alpha) worst portfolio returns
  Both are POSITIVE scalars representing expected loss in the tail.
"""

import numpy as np
import pandas as pd


# ── basic performance ─────────────────────────────────────────────────────────

def compute_annualized_return(returns: pd.Series, periods_per_year: int = 252) -> float:
    """CAGR from daily return series."""
    n = len(returns.dropna())
    if n < 2:
        return 0.0
    cum = (1 + returns.dropna()).prod()
    return float(cum ** (periods_per_year / n) - 1.0)


def compute_annualized_vol(returns: pd.Series, periods_per_year: int = 252) -> float:
    return float(returns.dropna().std() * np.sqrt(periods_per_year))


def compute_sharpe(returns: pd.Series, rf_annual: float = 0.0, periods_per_year: int = 252) -> float:
    rf_daily = rf_annual / periods_per_year
    excess   = returns.dropna() - rf_daily
    vol      = excess.std()
    if vol < 1e-10:
        return 0.0
    return float(excess.mean() / vol * np.sqrt(periods_per_year))


def compute_max_drawdown(returns: pd.Series) -> float:
    """Returns MDD as a positive decimal (loss convention)."""
    cum   = (1 + returns.dropna()).cumprod()
    peak  = cum.cummax()
    dd    = (cum - peak) / peak
    return float(abs(dd.min()))


def compute_calmar(returns: pd.Series, periods_per_year: int = 252) -> float:
    ann_ret = compute_annualized_return(returns, periods_per_year)
    mdd     = compute_max_drawdown(returns)
    return float(ann_ret / mdd) if mdd > 1e-8 else 0.0


# ── Ulcer Index / Serenity Ratio ──────────────────────────────────────────────

def compute_ulcer_index(returns: pd.Series) -> float:
    """Ulcer Index = sqrt(mean(drawdown^2))."""
    cum  = (1 + returns.dropna()).cumprod()
    peak = cum.cummax()
    dd   = (cum - peak) / peak
    return float(np.sqrt(np.mean(dd ** 2)))


def compute_serenity_ratio(returns: pd.Series, rf_annual: float = 0.0, periods_per_year: int = 252) -> float:
    ui  = compute_ulcer_index(returns)
    mdd = compute_max_drawdown(returns)
    ann = compute_annualized_return(returns, periods_per_year)
    if ui < 1e-10 or mdd < 1e-10:
        return 0.0
    return float((ann - rf_annual) / (ui * mdd))


# ── CVaR / CDaR (loss convention) ─────────────────────────────────────────────

def compute_cvar(
    returns: pd.Series,
    alpha: float = 0.95,
) -> float:
    """
    CVaR_alpha in LOSS convention: positive value = expected loss in worst (1-alpha) tail.
    CVaR = -mean(returns <= VaR quantile)
    """
    r = returns.dropna().values
    if len(r) < 10:
        return 0.0
    var_threshold = np.quantile(r, 1 - alpha)
    tail          = r[r <= var_threshold]
    if len(tail) == 0:
        return 0.0
    return float(-np.mean(tail))


def compute_cdar(
    returns: pd.Series,
    alpha: float = 0.95,
) -> float:
    """
    CDaR_alpha in LOSS convention: expected drawdown in worst (1-alpha) tail of drawdown distribution.
    """
    r   = returns.dropna().values
    if len(r) < 10:
        return 0.0
    cum  = np.cumprod(1 + r)
    peak = np.maximum.accumulate(cum)
    dd   = (peak - cum) / peak  # positive = loss

    var_threshold = np.quantile(dd, alpha)
    tail          = dd[dd >= var_threshold]
    if len(tail) == 0:
        return 0.0
    return float(np.mean(tail))


# ── factor risk contribution ──────────────────────────────────────────────────

def compute_factor_risk_contribution(
    weights: pd.Series,
    B_orth: pd.DataFrame,
    F: pd.DataFrame,
    sigma_spec: pd.Series,
) -> pd.Series:
    """
    Decomposes portfolio risk into factor vs. specific contributions (% of total var).
    Returns a dict-like Series: factor names + "specific".
    """
    tickers  = weights.index.tolist()
    w        = weights.reindex(tickers).fillna(0.0).values
    B_arr    = B_orth.reindex(tickers).fillna(0.0).values
    F_arr    = F.values

    factor_cov_n  = B_arr @ F_arr @ B_arr.T
    spec_var_n    = np.diag(sigma_spec.reindex(tickers).fillna(0.0).values ** 2 / 252)

    factor_var_port  = float(w @ factor_cov_n @ w)
    specific_var_port = float(w @ spec_var_n @ w)
    total_var         = factor_var_port + specific_var_port

    if total_var < 1e-12:
        return pd.Series({"factor": 0.0, "specific": 0.0})

    factor_by_col = {}
    for i, col in enumerate(B_orth.columns):
        beta_i = B_arr[:, i]
        f_ii   = F_arr[i, i]
        contrib = float((w * beta_i).sum() ** 2 * f_ii) / total_var
        factor_by_col[col] = contrib

    factor_by_col["specific"] = float(specific_var_port / total_var)
    return pd.Series(factor_by_col)


# ── exposure summaries ────────────────────────────────────────────────────────

def compute_exposure_summary(
    weights: pd.Series,
    metadata_df: pd.DataFrame,
) -> dict:
    """
    Returns country/sector/currency/sleeve exposure in a single dict of Series.
    """
    w = weights.reindex(metadata_df.index).fillna(0.0)

    def _agg(col):
        if col not in metadata_df.columns:
            return pd.Series(dtype=float)
        return w.groupby(metadata_df[col].fillna("Unknown")).sum().sort_values(ascending=False)

    return {
        "country":  _agg("country"),
        "sector":   _agg("sector"),
        "currency": _agg("trading_currency"),
        "sleeve":   _agg("sleeve"),
    }


# ── full resilience suite ─────────────────────────────────────────────────────

def calculate_resilience_suite(
    portfolio_returns: pd.Series,
    rf_annual: float = 0.0,
    cvar_alpha: float = 0.95,
    periods_per_year: int = 252,
) -> dict:
    """
    Full suite of performance and risk metrics from a portfolio return series.
    CVaR/CDaR are reported in loss convention (positive = loss).
    """
    r = portfolio_returns.dropna()
    return {
        "annualized_return":  compute_annualized_return(r, periods_per_year),
        "annualized_vol":     compute_annualized_vol(r, periods_per_year),
        "sharpe_ratio":       compute_sharpe(r, rf_annual, periods_per_year),
        "max_drawdown":       compute_max_drawdown(r),
        "calmar_ratio":       compute_calmar(r, periods_per_year),
        "ulcer_index":        compute_ulcer_index(r),
        "serenity_ratio":     compute_serenity_ratio(r, rf_annual, periods_per_year),
        f"cvar_{int(cvar_alpha*100)}":  compute_cvar(r, cvar_alpha),
        f"cdar_{int(cvar_alpha*100)}":  compute_cdar(r, cvar_alpha),
    }


def compute_portfolio_returns_from_vbt(vbt_pf) -> pd.Series:
    """
    Extracts daily portfolio returns from a vectorbt Portfolio object.
    Compatible with both old and new vectorbt APIs.
    """
    try:
        ret = vbt_pf.returns()
    except Exception:
        try:
            ret = vbt_pf.daily_returns()
        except Exception:
            ret = pd.Series(dtype=float)

    if hasattr(ret, "to_pandas"):
        ret = ret.to_pandas()
    return ret
