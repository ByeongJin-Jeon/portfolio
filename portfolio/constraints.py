# -*- coding: utf-8 -*-
"""
portfolio/constraints.py
========================
Formal constraint builder for the constrained QP optimizer.

Produces cvxpy-compatible constraint lists for:
  - Box constraints (per-asset min/max weight)
  - Country exposure bands
  - Sector exposure bands
  - Currency exposure bands
  - Sleeve floor/cap constraints (macro-conditioned)
  - Liquidity participation-rate caps
  - Full investment (sum of weights = 1)
"""

import numpy as np
import pandas as pd
import cvxpy as cp
from config import (
    LIQUIDITY_WINDOW, MAX_WEIGHT_SINGLE, MIN_WEIGHT_SINGLE,
    SLEEVE_DEFINITIONS, ETF_SHELTER_TICKERS,
    MIN_WEIGHT_USD, MAX_WEIGHT_USD, MIN_WEIGHT_KRW, MAX_WEIGHT_KRW,
    COUNTRY_BOUNDS, SECTOR_BOUNDS,
)


def build_box_constraints(
    w: cp.Variable,
    tickers: list,
    liquidity_caps: pd.Series,
) -> list:
    """
    Per-asset lower and upper bounds.
    ETF shelter assets use config ETF min/max; equity uses single-asset bounds.
    Liquidity cap provides an additional upper bound.
    """
    constraints = []
    n = len(tickers)

    w_min = np.full(n, MIN_WEIGHT_SINGLE)
    w_max = np.full(n, MAX_WEIGHT_SINGLE)

    for i, ticker in enumerate(tickers):
        if ticker in ETF_SHELTER_TICKERS:
            w_min[i] = 0.0
        if ticker in liquidity_caps.index:
            cap = float(liquidity_caps.loc[ticker])
            if np.isfinite(cap) and cap > 0:
                w_max[i] = min(w_max[i], cap)

    constraints.append(w >= w_min)
    constraints.append(w <= w_max)
    return constraints


def build_country_constraints(
    w: cp.Variable,
    tickers: list,
    metadata_df: pd.DataFrame,
    country_bounds: dict | None = None,
) -> list:
    """
    Sum of weights per country within [country_min, country_max].
    country_bounds = {"US": {"min": 0.20, "max": 0.80}, ...}
    """
    if country_bounds is None:
        country_bounds = COUNTRY_BOUNDS

    constraints = []
    countries = metadata_df.get("country", pd.Series(dtype=str))

    for country, bounds in country_bounds.items():
        mask = np.array([1.0 if countries.get(t) == country else 0.0 for t in tickers])
        if mask.sum() == 0:
            continue
        country_weight = mask @ w
        constraints.append(country_weight >= bounds.get("min", 0.0))
        constraints.append(country_weight <= bounds.get("max", 1.0))

    return constraints


def build_sector_constraints(
    w: cp.Variable,
    tickers: list,
    metadata_df: pd.DataFrame,
    sector_bounds: dict | None = None,
) -> list:
    """
    Sum of weights per sector within [sector_min, sector_max].
    Only non-ETF assets are counted toward sector exposure.
    """
    if sector_bounds is None:
        sector_bounds = SECTOR_BOUNDS

    constraints = []
    sectors = metadata_df.get("sector", pd.Series(dtype=str))
    is_etf  = {t: (t in ETF_SHELTER_TICKERS) for t in tickers}

    for sector, bounds in sector_bounds.items():
        mask = np.array([
            1.0 if (sectors.get(t) == sector and not is_etf.get(t, False)) else 0.0
            for t in tickers
        ])
        if mask.sum() == 0:
            continue
        sector_weight = mask @ w
        constraints.append(sector_weight >= bounds.get("min", 0.0))
        constraints.append(sector_weight <= bounds.get("max", 1.0))

    return constraints


def build_currency_constraints(
    w: cp.Variable,
    tickers: list,
    metadata_df: pd.DataFrame,
    ccy_bounds: dict | None = None,
) -> list:
    """
    Currency exposure bands: sum of weights for assets denominated in each currency.
    ccy_bounds = {"USD": {"min": 0.30, "max": 0.80}, "KRW": {"min": 0.10, "max": 0.60}}
    """
    if ccy_bounds is None:
        ccy_bounds = {
            "USD": {"min": MIN_WEIGHT_USD, "max": MAX_WEIGHT_USD},
            "KRW": {"min": MIN_WEIGHT_KRW, "max": MAX_WEIGHT_KRW},
        }

    constraints = []
    currencies = metadata_df.get("trading_currency", pd.Series(dtype=str))

    for ccy, bounds in ccy_bounds.items():
        mask = np.array([1.0 if currencies.get(t) == ccy else 0.0 for t in tickers])
        if mask.sum() == 0:
            continue
        ccy_weight = mask @ w
        constraints.append(ccy_weight >= bounds.get("min", 0.0))
        constraints.append(ccy_weight <= bounds.get("max", 1.0))

    return constraints


def build_sleeve_constraints(
    w: cp.Variable,
    tickers: list,
    metadata_df: pd.DataFrame,
    sleeve_bounds: dict | None = None,
) -> list:
    """
    Sleeve floor/cap constraints.
    sleeve_bounds passed in are already macro-adjusted by the constraint governor.
    Falls back to SLEEVE_DEFINITIONS if None.
    """
    if sleeve_bounds is None:
        sleeve_bounds = SLEEVE_DEFINITIONS

    constraints = []
    sleeves = metadata_df.get("sleeve", pd.Series(dtype=str))

    for sleeve, bounds in sleeve_bounds.items():
        mask = np.array([1.0 if sleeves.get(t) == sleeve else 0.0 for t in tickers])
        if mask.sum() == 0:
            continue
        sleeve_weight = mask @ w
        constraints.append(sleeve_weight >= bounds.get("min", 0.0))
        constraints.append(sleeve_weight <= bounds.get("max", 1.0))

    return constraints


def build_full_investment_constraint(w: cp.Variable) -> list:
    """Ensures portfolio is fully invested: sum(w) == 1."""
    return [cp.sum(w) == 1.0]


def compute_liquidity_caps(
    volume_df: pd.DataFrame,
    price_df: pd.DataFrame,
    nav: float,
    participation_rate: float = 0.01,
) -> pd.Series:
    """
    Liquidity participation-rate cap: w_i <= (ADV_i * participation_rate) / NAV
    ADV computed as max(short_term, 10th percentile long-term) to handle panic episodes.
    """
    short_term = volume_df.tail(LIQUIDITY_WINDOW).mean()
    long_term  = volume_df.tail(252).quantile(0.10)
    effective  = pd.concat([short_term, long_term], axis=1).max(axis=1)

    avg_price   = price_df.tail(LIQUIDITY_WINDOW).mean()
    capacity    = effective * avg_price * participation_rate
    caps        = (capacity / nav).clip(upper=MAX_WEIGHT_SINGLE)

    for ticker in caps.index:
        if ticker in ETF_SHELTER_TICKERS:
            caps[ticker] = MAX_WEIGHT_SINGLE

    return caps


def build_all_constraints(
    w: cp.Variable,
    tickers: list,
    metadata_df: pd.DataFrame,
    liquidity_caps: pd.Series,
    sleeve_bounds: dict | None = None,
    ccy_bounds: dict | None = None,
) -> list:
    """
    Assembles the full constraint list for the QP optimizer.
    """
    constraints = []
    constraints += build_full_investment_constraint(w)
    constraints += build_box_constraints(w, tickers, liquidity_caps)
    constraints += build_sleeve_constraints(w, tickers, metadata_df, sleeve_bounds)
    constraints += build_currency_constraints(w, tickers, metadata_df, ccy_bounds)
    constraints += build_country_constraints(w, tickers, metadata_df)
    constraints += build_sector_constraints(w, tickers, metadata_df)
    return constraints
