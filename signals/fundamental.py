# -*- coding: utf-8 -*-
"""
signals/fundamental.py
=======================
Primary alpha engine for individual equity securities ONLY.

ETF shelter assets are excluded before any scoring.
mu_ETF = 0 is assigned in the main pipeline orchestration.

Pipeline:
  build_fundamental_snapshot_table  (equity tickers only)
    -> compute_*_features
    -> normalize_alpha_features   (cross-sectional Z-score)
    -> build_composite_score      -> z_i (dimensionless)
    -> scale_to_expected_return   -> mu_i = IC * sigma_i * z_i (annualized decimal)

Missing data is tracked via data_quality_score, which feeds the u_i uncertainty penalty.
"""

import time
import numpy as np
import pandas as pd
import yfinance as yf
from config import ALPHA_WEIGHTS, IC_INITIAL, DART_API_KEY, ETF_SHELTER_TICKERS


# ── data fetch helpers ────────────────────────────────────────────────────────

def _safe(d: dict, key: str, default=np.nan) -> float:
    v = d.get(key)
    if v is None:
        return default
    try:
        f = float(v)
        return default if np.isnan(f) or np.isinf(f) else f
    except (TypeError, ValueError):
        return default


def _fetch_yf_info(ticker: str) -> dict:
    try:
        return yf.Ticker(ticker).info or {}
    except Exception:
        return {}


def fetch_fundamental_snapshot(ticker: str) -> dict:
    """Fetches raw fundamental data for a single equity ticker."""
    info = _fetch_yf_info(ticker)
    return {"ticker": ticker, "info": info}


def build_fundamental_snapshot_table(tickers: list) -> pd.DataFrame:
    """
    Fetches fundamentals for equity-only tickers.
    ETF shelter assets are excluded before fetching.
    Returns a flat DataFrame with one row per equity ticker.
    """
    equity_tickers = [t for t in tickers if t not in ETF_SHELTER_TICKERS]
    rows = []
    for ticker in equity_tickers:
        info = _fetch_yf_info(ticker)
        mc   = _safe(info, "marketCap")
        ta   = _safe(info, "totalAssets")
        ocf  = _safe(info, "operatingCashflow")
        ni   = _safe(info, "netIncomeToCommon")
        ebitda = _safe(info, "ebitda")
        int_exp = abs(_safe(info, "interestExpense", 0.0))
        capex   = abs(_safe(info, "capitalExpenditures", 0.0))

        rows.append({
            "ticker":               ticker,
            # Valuation
            "earnings_yield":       _safe(info, "trailingEps") / _safe(info, "previousClose", np.nan),
            "fcf_yield":            _safe(info, "freeCashflow") / mc,
            "op_yield":             ocf / mc,
            "book_to_price":        1.0 / _safe(info, "priceToBook", np.nan),
            # Quality / profitability
            "gross_profit_to_assets": _safe(info, "grossProfits") / ta,
            "roe":                  _safe(info, "returnOnEquity"),
            "roa":                  _safe(info, "returnOnAssets"),
            "ocf_to_net_income":    ocf / ni,
            "operating_margin":     _safe(info, "operatingMargins"),
            # Balance sheet
            "neg_debt_to_equity":   -_safe(info, "debtToEquity"),   # negated: lower D/E is better
            "current_ratio":        _safe(info, "currentRatio"),
            "interest_coverage":    ebitda / int_exp if int_exp > 0 else np.nan,
            "cash_to_assets":       _safe(info, "totalCash") / ta,
            # Capital discipline
            "neg_capex_to_ocf":     -(capex / ocf) if ocf > 0 else np.nan,  # negated: lower capex burden is better
            "neg_payout_ratio":     -_safe(info, "payoutRatio"),             # negated: lower payout = more retention
        })
        time.sleep(0.08)

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).set_index("ticker")


# ── feature engineering ───────────────────────────────────────────────────────

def compute_valuation_features(snapshot_df: pd.DataFrame) -> pd.DataFrame:
    cols = ["earnings_yield", "fcf_yield", "op_yield", "book_to_price"]
    return snapshot_df[[c for c in cols if c in snapshot_df.columns]].copy()


def compute_quality_features(snapshot_df: pd.DataFrame) -> pd.DataFrame:
    cols = ["gross_profit_to_assets", "roe", "roa", "ocf_to_net_income", "operating_margin"]
    return snapshot_df[[c for c in cols if c in snapshot_df.columns]].copy()


def compute_balance_sheet_features(snapshot_df: pd.DataFrame) -> pd.DataFrame:
    cols = ["neg_debt_to_equity", "current_ratio", "interest_coverage", "cash_to_assets"]
    return snapshot_df[[c for c in cols if c in snapshot_df.columns]].copy()


def compute_capital_discipline_features(snapshot_df: pd.DataFrame) -> pd.DataFrame:
    cols = ["neg_capex_to_ocf", "neg_payout_ratio"]
    return snapshot_df[[c for c in cols if c in snapshot_df.columns]].copy()


# ── normalization ─────────────────────────────────────────────────────────────

def normalize_alpha_features(
    feature_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Cross-sectional Z-score normalization.
    Returns (normalized_df, data_quality_series).
    data_quality_series ranges 0–1: 1.0 = fully observed, 0.0 = all missing.
    """
    n_cols   = feature_df.shape[1]
    n_miss   = feature_df.isna().sum(axis=1)
    quality  = 1.0 - (n_miss / max(n_cols, 1))

    normed = feature_df.copy()
    for col in normed.columns:
        obs = normed[col].dropna()
        if len(obs) < 3:
            normed[col] = 0.0
            continue
        mu_c  = obs.mean()
        std_c = obs.std()
        if std_c < 1e-8:
            normed[col] = 0.0
        else:
            normed[col] = (normed[col] - mu_c) / std_c

    normed = normed.clip(-3.0, 3.0).fillna(0.0)
    return normed, quality.rename("data_quality_score")


# ── composite scoring ─────────────────────────────────────────────────────────

def build_composite_score(
    normed_df: pd.DataFrame,
    alpha_weights: dict | None = None,
) -> pd.Series:
    """
    Produces dimensionless cross-sectional composite Z-score z_i.
    Equal-weight average within each family, then weighted across families.
    """
    if alpha_weights is None:
        alpha_weights = ALPHA_WEIGHTS

    families = {
        "valuation":          ["earnings_yield", "fcf_yield", "op_yield", "book_to_price"],
        "quality":            ["gross_profit_to_assets", "roe", "roa", "ocf_to_net_income", "operating_margin"],
        "balance_sheet":      ["neg_debt_to_equity", "current_ratio", "interest_coverage", "cash_to_assets"],
        "capital_discipline": ["neg_capex_to_ocf", "neg_payout_ratio"],
    }

    z = pd.Series(0.0, index=normed_df.index)
    for family, cols in families.items():
        avail = [c for c in cols if c in normed_df.columns]
        if not avail:
            continue
        z += alpha_weights.get(family, 0.0) * normed_df[avail].mean(axis=1)

    std = z.std()
    if std > 1e-8:
        z = z / std
    return z.rename("composite_z")


# ── IC scaling ────────────────────────────────────────────────────────────────

def scale_to_expected_return(
    z: pd.Series,
    sigma_spec: pd.Series,
    ic: float = IC_INITIAL,
) -> pd.Series:
    """
    Grinold-Kahn IC scaling: mu_i = IC * sigma_i * z_i.

    Parameters
    ----------
    z          : dimensionless composite Z-score per equity asset
    sigma_spec : annualized specific risk sqrt(D_ii) from the factor risk model
    ic         : information coefficient (assumed IC_INITIAL until calibrated)

    Returns
    -------
    mu : expected annualized excess return in decimal units
    """
    sigma_aligned = sigma_spec.reindex(z.index).fillna(sigma_spec.median() if not sigma_spec.empty else 0.15)
    return (ic * sigma_aligned * z).rename("mu")


# ── full pipeline ─────────────────────────────────────────────────────────────

def build_expected_return_vector(
    snapshot_df: pd.DataFrame,
    sigma_spec_series: pd.Series,
    alpha_weights: dict | None = None,
    ic: float = IC_INITIAL,
) -> tuple[pd.Series, pd.Series, pd.DataFrame]:
    """
    Full pipeline: snapshot_df -> z_i -> mu_i.

    Returns
    -------
    mu_series          : expected annualized excess return per equity ticker
    composite_z_series : dimensionless composite Z-score
    data_quality_df    : missingness-based data quality score per ticker
    """
    if snapshot_df.empty:
        empty = pd.Series(dtype=float)
        return empty, empty, pd.DataFrame()

    combined = pd.concat([
        compute_valuation_features(snapshot_df),
        compute_quality_features(snapshot_df),
        compute_balance_sheet_features(snapshot_df),
        compute_capital_discipline_features(snapshot_df),
    ], axis=1)

    normed, data_quality = normalize_alpha_features(combined)
    z  = build_composite_score(normed, alpha_weights)
    mu = scale_to_expected_return(z, sigma_spec_series, ic)

    return mu, z, data_quality.to_frame()
