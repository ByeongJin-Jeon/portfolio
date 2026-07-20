# -*- coding: utf-8 -*-
"""
optimization/mean_risk.py
=========================
Primary constrained QP optimizer using cvxpy.

Objective:
  minimize  -mu_tilde' w + lambda_r * quad_form(w, Sigma) + lambda_h * sum_squares(w - w_ref)

Subject to:
  sum(w) == 1
  box constraints
  sleeve floors/caps (macro-conditioned)
  country/sector/currency bands
  liquidity participation-rate caps
  CVaR(w) <= L_cvar   (loss convention, tail-risk overlay)
  CDaR(w) <= L_cdar   (loss convention, tail-risk overlay)

Loss convention (consistent with Riskfolio-Lib):
  CVaR_alpha(w) = -1/(T*(1-alpha)) * sum of T*(1-alpha) worst returns of w'r_t
  Both L_cvar and L_cdar are POSITIVE scalars (losses bounded above).
"""

import warnings
import numpy as np
import pandas as pd
import cvxpy as cp
from config import (
    OPTIMIZER_RISK_AVERSION, OPTIMIZER_HOLDING_REG,
    CVAR_LIMIT, CDAR_LIMIT, CVAR_ALPHA,
)
from portfolio.constraints import build_all_constraints


def _build_cvar_constraints(
    w: cp.Variable,
    returns_matrix: np.ndarray,
    cvar_limit: float,
    alpha: float,
) -> list:
    """
    Adds a linear CVaR constraint in the loss convention.

    CVaR_alpha(w) <= cvar_limit

    Via Rockafellar-Uryasev:
      CVaR = zeta + 1/((1-alpha)*T) * sum(s_t)
      s_t  >= -r_t' w - zeta
      s_t  >= 0

    Here r_t are daily returns (rows of returns_matrix).
    The constraint is cast with losses = -r_t (positive = loss).
    """
    T, n = returns_matrix.shape
    zeta = cp.Variable(nonneg=False)
    s    = cp.Variable(T, nonneg=True)

    R = returns_matrix  # (T x n), positive = gain

    constraints = [
        s >= -R @ w - zeta,
        zeta + cp.sum(s) / ((1 - alpha) * T) <= cvar_limit,
    ]
    return constraints, [zeta, s]


def _build_cdar_constraints(
    w: cp.Variable,
    returns_matrix: np.ndarray,
    cdar_limit: float,
    alpha: float,
) -> list:
    """
    Adds a linear CDaR constraint in the loss convention.

    CDaR_alpha(w) <= cdar_limit

    Portfolio cumulative drawdown D_t(w) = max_{0<=s<=t}(W_s) - W_t
    where W_t = prod(1 + r_s w) ≈ 1 + sum(r_s w) (log-linear approx).

    Linear formulation (Chekhlov, Uryasev, Zabarankin 2005):
      u_t >= u_{t-1} + r_t w                (running max)
      u_t >= 1                               (floor at initial wealth)
      d_t  = u_t - (1 + cumulative(r w))   (drawdown approximation)
      CDaR = eta + 1/((1-alpha)*T) * sum(z_t)
      z_t  >= d_t - eta
      z_t  >= 0
    """
    T, n = returns_matrix.shape

    u    = cp.Variable(T + 1, nonneg=True)  # running maximum, index 0 = t=0
    z    = cp.Variable(T, nonneg=True)
    eta  = cp.Variable(nonneg=True)

    # Cumulative portfolio returns (approximate, linear)
    # L is a constant (T x T) lower-triangular matrix of ones.
    # L @ x  gives the prefix sums of x without building a chain in CVXPY.
    L       = np.tril(np.ones((T, T)))          # constant, built once in numpy
    cum_ret = L @ (returns_matrix @ w)           # single CVXPY matmul, shape (T,)
    # cum_ret = cp.cumsum(returns_matrix @ w)  # length T

    # Vectorised (O(1) CVXPY objects, O(T) problem data):
    constraints = [
        u[0] == 1.0,
        u[1:] >= u[:-1],            # running-max monotonicity: one vector constraint
        u[1:] >= 1 + cum_ret,       # floor at 1 + cumulative return: one vector constraint
    ]
    d_t = u[1:] - (1 + cum_ret)

    constraints += [
        z >= d_t - eta,
        eta + cp.sum(z) / ((1 - alpha) * T) <= cdar_limit,
    ]
    return constraints, [u, z, eta]


def solve_mean_risk(
    mu_tilde: pd.Series,
    Sigma: pd.DataFrame,
    tickers: list,
    metadata_df: pd.DataFrame,
    liquidity_caps: pd.Series,
    returns_df: pd.DataFrame | None = None,
    w_ref: pd.Series | None = None,
    lambda_r: float = OPTIMIZER_RISK_AVERSION,
    lambda_h: float = OPTIMIZER_HOLDING_REG,
    sleeve_bounds: dict | None = None,
    ccy_bounds: dict | None = None,
    apply_cvar: bool = True,
    apply_cdar: bool = True,
    cvar_limit: float = CVAR_LIMIT,
    cdar_limit: float = CDAR_LIMIT,
    cvar_alpha: float = CVAR_ALPHA,
    solver: str = "CLARABEL",
    verbose: bool = False,
) -> tuple[pd.Series, str, dict]:
    """
    Solves the constrained mean-risk QP.

    Returns
    -------
    weights  : pd.Series of optimal weights
    status   : solver status string
    meta     : dict with objective, risk, CVaR, CDaR values
    """
    n = len(tickers)
    w = cp.Variable(n)

    mu_arr = mu_tilde.reindex(tickers).fillna(0.0).values
    S      = Sigma.reindex(tickers, columns=tickers).fillna(0.0).values
    S      = (S + S.T) / 2.0 + np.eye(n) * 1e-8

    if w_ref is None:
        w_ref_arr = np.ones(n) / n
    else:
        w_ref_arr = w_ref.reindex(tickers).fillna(1.0 / n).values

    # ── objective ──────────────────────────────────────────────────────────────
    alpha_term   = -mu_arr @ w
    risk_term    = lambda_r * cp.quad_form(w, cp.psd_wrap(S))
    holding_term = lambda_h * cp.sum_squares(w - w_ref_arr)
    objective    = cp.Minimize(alpha_term + risk_term + holding_term)

    # ── structural constraints ─────────────────────────────────────────────────
    constraints = build_all_constraints(
        w, tickers, metadata_df, liquidity_caps, sleeve_bounds, ccy_bounds
    )

    # ── tail-risk overlay ──────────────────────────────────────────────────────
    aux_vars = []
    if returns_df is not None and (apply_cvar or apply_cdar):
        ret_arr = returns_df.reindex(columns=tickers).fillna(0.0).values
        T_ret   = ret_arr.shape[0]
        if T_ret >= 50:
            if apply_cvar:
                cvar_cons, aux_c = _build_cvar_constraints(w, ret_arr, cvar_limit, cvar_alpha)
                constraints += cvar_cons
                aux_vars    += aux_c
            if apply_cdar:
                cdar_cons, aux_d = _build_cdar_constraints(w, ret_arr, cdar_limit, cvar_alpha)
                constraints += cdar_cons
                aux_vars    += aux_d

    prob = cp.Problem(objective, constraints)

    # ── solve with fallback ────────────────────────────────────────────────────
    status = _solve_with_fallback(prob, solver, verbose)

    if w.value is None:
        weights = pd.Series(1.0 / n, index=tickers)
        return weights, status, {"error": "solver_failed"}

    w_opt = np.array(w.value).flatten()
    w_opt = np.maximum(w_opt, 0.0)
    w_opt /= w_opt.sum()
    weights = pd.Series(w_opt, index=tickers)

    port_vol  = float(np.sqrt(max(w_opt @ S @ w_opt, 0.0)))
    port_ret  = float(mu_arr @ w_opt)

    meta = {
        "objective":  float(prob.value) if prob.value is not None else np.nan,
        "port_vol":   port_vol,
        "port_ret":   port_ret,
        "status":     status,
    }
    return weights, status, meta


def _solve_with_fallback(
    problem: cp.Problem,
    solver: str = "CLARABEL",
    verbose: bool = False,
) -> str:
    """
    Tries the primary solver; falls back through ECOS → SCS → equal-weight.
    Returns the final solver status string.
    """
    solver_chain = [solver, "ECOS", "SCS"]
    for s in solver_chain:
        try:
            problem.solve(solver=s, verbose=verbose)
            if problem.status in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
                return problem.status
        except cp.error.SolverError:
            continue
        except Exception:
            continue

    return problem.status or "unknown_failure"
