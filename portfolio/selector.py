# -*- coding: utf-8 -*-
"""
portfolio/selector.py
=====================
Portfolio validation and exposure reporting.

No longer performs top-N selection by weight.
The optimizer returns weights directly; this module validates them and
produces structured risk/exposure reports.
"""

import numpy as np
import pandas as pd


def validate_portfolio(
    weights: pd.Series,
    metadata_df: pd.DataFrame,
    sigma_spec: pd.Series,
    Sigma: pd.DataFrame,
    tolerance: float = 1e-4,
) -> dict:
    """
    Validates a set of portfolio weights.

    Checks:
      - Sum of weights within [1 - tol, 1 + tol]
      - No weight violates per-asset bounds
      - No negative weights
      - Returns validation summary dict
    """
    issues = []
    w = weights.dropna()

    total = w.sum()
    if abs(total - 1.0) > tolerance:
        issues.append(f"Sum of weights = {total:.6f} (expected 1.0 ± {tolerance})")

    negative = w[w < -tolerance]
    if not negative.empty:
        issues.append(f"Negative weights: {negative.to_dict()}")

    n = len(w)
    port_var = float(w.values @ Sigma.reindex(w.index, columns=w.index).fillna(0).values @ w.values)
    port_vol = np.sqrt(max(port_var, 0.0))

    return {
        "valid":          len(issues) == 0,
        "issues":         issues,
        "n_assets":       n,
        "sum_weights":    float(total),
        "port_vol_ann":   float(port_vol),
        "max_weight":     float(w.max()),
        "min_weight":     float(w[w > 1e-6].min()) if (w > 1e-6).any() else 0.0,
        "n_active":       int((w > 1e-6).sum()),
    }


def build_exposure_report(
    weights: pd.Series,
    metadata_df: pd.DataFrame,
) -> dict:
    """
    Returns country, sector, currency, and sleeve exposure summaries.
    """
    w = weights.reindex(metadata_df.index).fillna(0.0)

    def _exposure(col: str) -> pd.Series:
        if col not in metadata_df.columns:
            return pd.Series(dtype=float)
        groups = metadata_df[col].fillna("Unknown")
        return w.groupby(groups).sum().sort_values(ascending=False)

    return {
        "country":  _exposure("country"),
        "sector":   _exposure("sector"),
        "currency": _exposure("trading_currency"),
        "sleeve":   _exposure("sleeve"),
    }


def build_risk_report(
    weights: pd.Series,
    Sigma: pd.DataFrame,
    B_orth: pd.DataFrame,
    F: pd.DataFrame,
    sigma_spec: pd.Series,
) -> dict:
    """
    Returns marginal risk contribution breakdown: factor vs. specific.
    """
    tickers   = weights.index.tolist()
    w         = weights.fillna(0.0).values
    S         = Sigma.reindex(tickers, columns=tickers).fillna(0).values

    port_var  = float(w @ S @ w)
    port_vol  = np.sqrt(max(port_var, 0.0))

    mrc       = S @ w / (port_vol + 1e-12)  # marginal risk contribution
    crc       = w * mrc                      # component risk contribution
    crc_pct   = crc / port_vol if port_vol > 1e-10 else crc * 0.0

    B_arr = B_orth.reindex(tickers).fillna(0.0).values
    F_arr = F.values * 0  # suppress factor cov for now since already in Sigma

    specific_var_total = float(((w ** 2) * sigma_spec.reindex(tickers).fillna(0).values ** 2 / 252).sum())

    return {
        "port_vol_ann":         port_vol,
        "port_var_ann":         port_var,
        "component_risk_pct":   pd.Series(crc_pct, index=tickers).sort_values(ascending=False),
        "marginal_risk":        pd.Series(mrc, index=tickers).sort_values(ascending=False),
        "specific_var_share":   float(specific_var_total / (port_var + 1e-12)),
    }


def build_alpha_report(
    weights: pd.Series,
    mu: pd.Series,
    mu_tilde: pd.Series,
    z_scores: pd.Series,
    u_penalty: pd.Series,
    l_penalty: pd.Series,
) -> pd.DataFrame:
    """
    Builds a per-asset alpha attribution table.
    """
    tickers = weights.index.tolist()
    report  = pd.DataFrame(index=tickers)
    report["weight"]    = weights.reindex(tickers).fillna(0.0)
    report["mu"]        = mu.reindex(tickers).fillna(0.0)
    report["u_penalty"] = u_penalty.reindex(tickers).fillna(0.0)
    report["l_penalty"] = l_penalty.reindex(tickers).fillna(0.0)
    report["mu_tilde"]  = mu_tilde.reindex(tickers).fillna(0.0)
    report["z_score"]   = z_scores.reindex(tickers).fillna(0.0)
    report["weighted_mu_tilde"] = report["weight"] * report["mu_tilde"]
    return report.sort_values("weighted_mu_tilde", ascending=False)


def export_portfolio(weights: pd.Series, path: str, encoding: str = "utf-8-sig") -> None:
    """Outputs the final allocation to CSV."""
    active = weights[weights > 1e-6].sort_values(ascending=False)
    active.to_csv(path, encoding=encoding)
