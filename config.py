# -*- coding: utf-8 -*-
"""
config.py
=========
Single source of truth for all constants, thresholds, and universe definitions.

Architecture: IC-scaled fundamental alpha + orthogonalized factor risk model +
              constrained QP optimizer + ETF shelter sleeve floors + CVaR/CDaR overlay.
"""

import os
from pathlib import Path

# ============================================================
# DATA PIPELINE
# ============================================================
USE_CACHE_DATA = True
DART_API_KEY   = "013401953d0a2a176ebd48d36f204a73b7033107"

# ============================================================
# PATHS
# ============================================================
BASE_DIR     = Path(__file__).resolve().parent
DATA_DIR     = BASE_DIR / "data" / "cache"
OUTPUT_DIR   = BASE_DIR / "outputs"
SNAPSHOT_DIR = BASE_DIR / "outputs" / "snapshots"
LOG_DIR      = BASE_DIR / "logs"

for _dir in [DATA_DIR, OUTPUT_DIR, SNAPSHOT_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)

# ============================================================
# ENCODING
# ============================================================
CSV_ENCODING = "utf-8-sig"
TICKER_NORM  = "NFC"

# ============================================================
# DATA WINDOW
# ============================================================
PRICE_START = "2006-01-01"
PRICE_END   = None

# ============================================================
# ALPHA MODEL
# ============================================================
# IC = cross-sectional Pearson correlation of z_i with realized forward returns.
# IC_INITIAL is an assumed value (not calibrated). Update by cross-validation
# as decision snapshots accumulate in SNAPSHOT_DIR.
IC_INITIAL = 0.04

ALPHA_WEIGHTS = {
    "valuation":          0.35,
    "quality":            0.25,
    "balance_sheet":      0.25,
    "capital_discipline": 0.15,
}

# ============================================================
# RISK MODEL
# ============================================================
COVARIANCE_WINDOW     = 252    # trading days
EWMA_HALFLIFE         = 63     # days (one quarter)
LEDOIT_WOLF_SHRINKAGE = True
SPECIFIC_RISK_FLOOR   = 1e-4   # minimum D_ii

# Gram-Schmidt orthogonalization order for factor exposure matrix B.
# Higher-priority groups are projected out of lower-priority columns.
FACTOR_PRIORITY = ["sleeve", "country", "sector", "currency"]

# ============================================================
# OPTIMIZER
# ============================================================
# lambda_r: CARA risk aversion. Interpretable as standard MV utility coefficient
# only after IC scaling makes mu dimensionally consistent (annualized decimal return units).
OPTIMIZER_RISK_AVERSION = 3.0
OPTIMIZER_HOLDING_REG   = 0.25   # lambda_h: holdings-stability regularizer
UNCERTAINTY_PENALTY     = 0.50   # gamma_u
LIQUIDITY_PENALTY       = 0.25   # gamma_l

# ============================================================
# PORTFOLIO CONSTRAINTS
# ============================================================
MAX_WEIGHT_SINGLE   = 0.10
MAX_WEIGHT_SECTOR   = 0.25
MAX_WEIGHT_COUNTRY  = 0.60
MAX_ASSETS          = 20
MIN_WEIGHT          = 0.01

MIN_WEIGHT_USD      = 0.30
MAX_WEIGHT_USD      = 0.70
MIN_WEIGHT_KRW      = 0.30
MAX_WEIGHT_KRW      = 0.70

MIN_WEIGHT_CASH              = 0.05
MIN_WEIGHT_BOND_CASH_STRESS  = 0.15

MAX_PARTICIPATION_RATE = 0.10   # kappa

# ============================================================
# CVaR / CDaR  (loss convention throughout: positive = worse)
# CVaR_alpha(w) <= L_cvar
# CDaR_alpha(w) <= L_cdar
# This is consistent with Riskfolio-Lib's interface.
# ============================================================
CVAR_ALPHA   = 0.05
CDAR_ALPHA   = 0.05
CVAR_LIMIT   = 0.20   # L_cvar: maximum expected tail loss (fraction)
CDAR_LIMIT   = 0.30   # L_cdar: maximum conditional drawdown (fraction)
RISK_FREE_RATE = 0.04

# ============================================================
# STRESS REGIME THRESHOLDS
# ============================================================
VIX_NORMAL_UPPER   = 20.0
VIX_ELEVATED_UPPER = 30.0
FX_VOL_STRESS      = 0.05

# ============================================================
# ETF SHELTER ARCHITECTURE
# ============================================================
ETF_SHELTER_TICKERS = [
    "TLT", "IEF", "SGOV", "GLD", "DBC",
    "114260.KS", "148070.KS", "456880.KS",
    "069500.KS", "139260.KS",
]

# Base sleeve bounds. Floors are tightened by macro risk governor under stress.
SLEEVE_DEFINITIONS = {
    "global_equity":        {"min": 0.20, "max": 0.80},
    "safe_haven_bond":      {"min": 0.05, "max": 0.40},
    "cash":                 {"min": 0.05, "max": 0.30},
    "safe_haven_commodity": {"min": 0.00, "max": 0.15},
    "commodity":            {"min": 0.00, "max": 0.15},
    "equity_index":         {"min": 0.00, "max": 0.20},
}

# Delta applied to sleeve floors by the macro risk governor under stress.
SLEEVE_STRESS_DELTA = {
    "elevated": {"safe_haven_bond": 0.05, "cash": 0.05},
    "stress":   {"safe_haven_bond": 0.10, "cash": 0.10, "safe_haven_commodity": 0.05},
    "fx_stress":{"cash": 0.05},
}

# ============================================================
# BACKTEST (historical price-mechanics replay only)
# Full structural alpha replay is not yet valid — requires historical
# fundamental snapshots stored in SNAPSHOT_DIR.
# ============================================================
BACKTEST_SCENARIOS = {
    "GFC_2008":    ("2007-07-01", "2009-06-30"),
    "COVID_2020":  ("2019-10-01", "2021-03-31"),
    "MIDEAST_2026":("2025-10-01", None),
}
BACKTEST_INITIAL_CAPITAL = 1_000_000
BACKTEST_COMMISSION      = 0.001
BACKTEST_ENABLE          = True

# ============================================================
# EVALUATION
# ============================================================
ULCER_WINDOW  = 14
CALMAR_WINDOW = 36

# ============================================================
# COUNTRY / SECTOR BOUNDS (used by constraints builder)
# ============================================================
COUNTRY_BOUNDS = {
    "US":  {"min": 0.10, "max": 0.70},
    "KR":  {"min": 0.10, "max": 0.70},
}

SECTOR_BOUNDS = {
    "Technology":        {"min": 0.00, "max": 0.25},
    "Financials":        {"min": 0.00, "max": 0.25},
    "Healthcare":        {"min": 0.00, "max": 0.25},
    "Consumer Cyclical": {"min": 0.00, "max": 0.20},
    "Industrials":       {"min": 0.00, "max": 0.20},
    "Energy":            {"min": 0.00, "max": 0.15},
    "Materials":         {"min": 0.00, "max": 0.15},
    "Communication Services": {"min": 0.00, "max": 0.20},
}

# ============================================================
# ADDITIONAL CONSTRAINT PARAMETERS
# ============================================================
MIN_WEIGHT_SINGLE = 0.00   # per-asset lower bound (long-only: 0.0)
LIQUIDITY_WINDOW  = 20     # trading days for short-term ADV calculation

# ============================================================
# HRP FALLBACK / BENCHMARK PARAMETERS
# ============================================================
HRP_LINKAGE_METHOD   = "ward"
HRP_DISTANCE_METRIC  = "pearson"

# ============================================================
# OPTIONAL BL FLAG
# ============================================================
ENABLE_BLACK_LITTERMAN = False

# ============================================================
# LEGACY — kept for backwards compat with any remaining imports.
# These are NOT used in the production pipeline.
# ============================================================
CORE_ETFS = [
    "SPY", "DBC", "VNQ", "XLK", "XLE", "XLV",
    "069500.KS", "139260.KS",
]
DEFENSIVE_ETFS = [
    "TLT", "IEF", "SHV", "SGOV", "GLD",
    "114260.KS", "148070.KS", "456880.KS",
]
