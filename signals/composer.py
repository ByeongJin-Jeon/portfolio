# -*- coding: utf-8 -*-
"""
signals/composer.py
===================
Pipeline assembler for the institutional alpha architecture.

Assembles:
  mu (IC-scaled fundamental alpha, equity only)
  u  (options-implied uncertainty penalty)
  l  (liquidity penalty)
  -> mu_tilde = mu - gamma_u * u - gamma_l * l

Also calls the macro risk governor to produce constraint multipliers.
No BL view composition. No trend signals. No defensive overrides.
"""

import numpy as np
import pandas as pd
from config import (
    UNCERTAINTY_PENALTY, LIQUIDITY_PENALTY,
    SLEEVE_DEFINITIONS, MIN_WEIGHT_USD, MAX_WEIGHT_USD,
    MIN_WEIGHT_KRW, MAX_WEIGHT_KRW,
)
from signals.fundamental import build_expected_return_vector
from signals.options_skew import build_uncertainty_penalty_vector
from signals.macro import get_macro_state, build_constraint_multipliers, apply_macro_constraint_adjustments


def build_liquidity_penalty_vector(
    candidate_df: pd.DataFrame,
    nav: float,
    gamma_l: float = LIQUIDITY_PENALTY,
) -> pd.Series:
    """
    Liquidity penalty l_i in annualized return units.
    Assets with low ADV relative to NAV receive a higher penalty.
    ETF shelter assets receive l_i = 0 (no liquidity friction assumed).
    """
    max_adv = candidate_df["adv"].replace(0, np.nan).max()
    if not np.isfinite(max_adv) or max_adv <= 0:
        return pd.Series(0.0, index=candidate_df.index, name="l_penalty")

    l = (1.0 - (candidate_df["adv"] / max_adv).clip(0, 1)) * gamma_l
    for ticker in candidate_df.index:
        if candidate_df.loc[ticker, "is_etf_shelter"]:
            l[ticker] = 0.0
    return l.rename("l_penalty")


def assemble_net_expected_return(
    snapshot_df: pd.DataFrame,
    sigma_spec_series: pd.Series,
    candidate_df: pd.DataFrame,
    nav: float,
    gamma_u: float = UNCERTAINTY_PENALTY,
    gamma_l: float = LIQUIDITY_PENALTY,
    ic: float | None = None,
    alpha_weights: dict | None = None,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """
    Assembles mu_tilde for all assets in the candidate frame.

    For equity assets:  mu_i = IC * sigma_i * z_i  (from fundamental model)
    For ETF assets:     mu_i = 0                    (no fundamental alpha)

    Then: mu_tilde_i = mu_i - gamma_u * u_i - gamma_l * l_i

    Returns
    -------
    mu_tilde : net expected return vector (annualized decimal)
    mu       : raw IC-scaled expected return (equity non-zero; ETF zero)
    u        : uncertainty penalty vector
    l        : liquidity penalty vector
    """
    from config import IC_INITIAL
    if ic is None:
        ic = IC_INITIAL

    all_tickers = candidate_df.index.tolist()

    # --- build mu ---
    equity_tickers = [t for t in all_tickers if not candidate_df.loc[t, "is_etf_shelter"]]
    equity_snap    = snapshot_df.reindex(equity_tickers) if not snapshot_df.empty else pd.DataFrame()

    mu_equity, _, _ = build_expected_return_vector(
        equity_snap, sigma_spec_series, alpha_weights, ic,
    )

    mu = pd.Series(0.0, index=all_tickers, name="mu")
    if not mu_equity.empty:
        mu.update(mu_equity)

    # --- build u ---
    u = build_uncertainty_penalty_vector(all_tickers)
    u = u.reindex(all_tickers).fillna(u.median() if not u.empty else 0.05)

    # --- build l ---
    l = build_liquidity_penalty_vector(candidate_df, nav, gamma_l)

    # --- assemble ---
    u_aligned = u.reindex(all_tickers).fillna(0.0)
    l_aligned = l.reindex(all_tickers).fillna(0.0)
    mu_tilde  = mu - gamma_u * u_aligned - l_aligned
    mu_tilde.name = "mu_tilde"

    return mu_tilde, mu, u_aligned, l_aligned


def get_constraint_adjustments(is_live: bool = True) -> dict:
    """
    Fetches live macro state and returns adjusted sleeve and currency bounds.
    In historical replay mode, returns base constraint bounds unchanged.
    """
    base_sleeve = SLEEVE_DEFINITIONS.copy()
    base_ccy = {
        "USD": {"min": MIN_WEIGHT_USD, "max": MAX_WEIGHT_USD},
        "KRW": {"min": MIN_WEIGHT_KRW, "max": MAX_WEIGHT_KRW},
    }

    if not is_live:
        return {
            "sleeve_bounds": base_sleeve,
            "ccy_bounds":    base_ccy,
            "macro_state":   {"vix_level": 20.0, "fx_vol": 0.0, "stress_regime": "normal"},
        }

    macro_state  = get_macro_state()
    multipliers  = build_constraint_multipliers(macro_state)
    adj_sleeve, adj_ccy = apply_macro_constraint_adjustments(
        base_sleeve, base_ccy, multipliers,
    )
    return {
        "sleeve_bounds": adj_sleeve,
        "ccy_bounds":    adj_ccy,
        "macro_state":   macro_state,
        "multipliers":   multipliers,
    }
