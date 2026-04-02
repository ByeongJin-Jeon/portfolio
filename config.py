# -*- coding: utf-8 -*-
"""
config.py
=========
Single source of truth for all constants, thresholds, and universe definitions.
Every other module imports from here — never hardcode values elsewhere.
"""

import os
from pathlib import Path

# ============================================================
# PATHS
# ============================================================
BASE_DIR   = Path(__file__).resolve().parent
DATA_DIR   = BASE_DIR / "data" / "cache"        # cached price CSVs
OUTPUT_DIR = BASE_DIR / "outputs"
LOG_DIR    = BASE_DIR / "logs"

for _dir in [DATA_DIR, OUTPUT_DIR, LOG_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)


# ============================================================
# ENCODING (Phase 2 — Korean Data Protocol)
# ============================================================
CSV_ENCODING   = "utf-8-sig"     # preserves BOM for Hangul on Windows / macOS
TICKER_NORM    = "NFC"           # unicodedata.normalize form for KRX ticker matching


# ============================================================
# DATA WINDOW
# ============================================================
PRICE_START    = "2006-01-01"    # enough history for 2008 crisis backtest
PRICE_END      = None            # None → fetch up to today


# ============================================================
# SIGNAL PARAMETERS (Phase 1-A — Trend)
# ============================================================
MA_PERIODS     = [5, 22, 60, 182]    # short → long moving average windows
ENVELOPE_PERIOD = 22                  # central MA for the envelope
ENVELOPE_BAND   = 0.10                # ±10 % bands around the 22-day MA

# Minimum alignment score to generate a BL view (0.0 – 1.0)
# Signals below this gate are excluded from the Omega matrix entirely
MIN_SIGNAL_STRENGTH = 0.25            # i.e., at least 1 of 4 MA conditions met


# ============================================================
# MACRO RISK FILTERS (Phase 1-B — McGee TAA)
# ============================================================
VIX_KILLSWITCH     = 25.0     # if VIX ≥ this, reduce equity beta
VIX_CONFIDENCE_BASE = 20.0    # VIX level at which the Omega scalar = 1.0
                               # above this, confidence linearly decays:
                               # scalar = 1 + max(0, (VIX - 20) / 20)

TIPS_TICKER         = "TIP"   # iShares TIPS Bond ETF as real-rate proxy
SOFR_SAFE_HAVEN     = "SGOV"  # rotate here during VIX kill-switch (US equiv)
                               # KRX equivalent: "ACE SOFR ETF" (229200.KS)


# ============================================================
# ASSET UNIVERSE (Phase 3 — Barbell Strategy)
# ============================================================

# --- Strategic KRX Holdings ---
KRX_TICKERS = {
    # Defensive Alpha (Defense)
    "012450.KS": "한화에어로스페이스",      # Hanwha Aerospace
    "079550.KS": "LIG넥스원",             # LIG Nex1

    # Supply Chain (Shipbuilding / Energy)
    "329180.KS": "HD현대중공업",           # HD Hyundai Heavy Industries

    # Safe Haven (Base Metals / Gold proxy)
    "010130.KS": "고려아연",               # Korea Zinc

    # Core / Liquid
    "005930.KS": "삼성전자",               # Samsung Electronics
}

# --- Strategic US Holdings ---
US_TICKERS = {
    # Defensive Alpha (Quality)
    "MSFT":  "Microsoft",
    "AAPL":  "Apple",

    # Supply Chain (Energy & Agriculture)
    "OXY":   "Oxidental Petroleum",
    "ADM":   "Archer-Daniels-Midland",
    "CTVA":  "Corteva",

    # Safe Haven (Gold Miners)
    "NEM":   "Newmont",
    "GOLD":  "Barrick Gold",

    # Core / Liquid (Consumer Staples)
    "JNJ":   "Johnson & Johnson",
    "PG":    "Procter & Gamble",
}

# Combined flat list for yfinance bulk download
ALL_STRATEGIC_TICKERS = list(KRX_TICKERS.keys()) + list(US_TICKERS.keys())

# Universe expansion (top-200 KOSPI + index constituents)
# Actual fetching happens in data/universe.py
KOSPI_TOP_N         = 200
US_INDICES          = ["sp500", "nasdaq100", "dowjones"]   # used by universe.py

# Segment mapping for HRP risk-block clustering
SEGMENT_MAP = {
    "012450.KS": "Defense",
    "079550.KS": "Defense",
    "329180.KS": "Energy",
    "010130.KS": "SafeHaven",
    "005930.KS": "Core",
    "MSFT":      "Quality",
    "AAPL":      "Quality",
    "XOM":       "Energy",
    "ADM":       "Agri",
    "CTVA":      "Agri",
    "NEM":       "SafeHaven",
    "GOLD":      "SafeHaven",
    "JNJ":       "Core",
    "PG":        "Core",
}


# ============================================================
# OPTIMIZATION PARAMETERS (Phase 2)
# ============================================================

# HRP
HRP_LINKAGE_METHOD  = "ward"          # scipy linkage method for dendrogram
HRP_DISTANCE_METRIC = "pearson"       # correlation → distance conversion

# Black-Litterman
BL_RISK_AVERSION    = 2.5             # δ (delta): market risk-aversion coefficient
BL_TAU              = 0.05            # τ (tau): scales uncertainty of prior
                                       # rule-of-thumb: 1/T where T = sample length

# CDaR / UPI
CDAR_ALPHA          = 0.95            # CVaR / CDaR confidence level
CDAR_LIMIT          = 0.15            # hard constraint: CDaR ≤ 15 %
RISK_FREE_RATE      = 0.04            # annualized (used in UPI & Calmar)


# ============================================================
# PORTFOLIO CONSTRAINTS (Phase 5)
# ============================================================
MAX_ASSETS          = 10              # final portfolio: top-N by weight
MIN_WEIGHT          = 0.01            # floor: 1 % per asset
MAX_WEIGHT_SINGLE   = 0.30            # ceiling: 30 % per asset
LIQUIDITY_WINDOW    = 20              # days for avg-volume weight cap


# ============================================================
# FAMA-FRENCH (Phase 5 — Factor Loading)
# ============================================================
FF_FACTORS          = 5               # 5-factor model (Mkt, SMB, HML, RMW, CMA)
FF_REGRESSION_WINDOW = 252            # rolling window in trading days (1 year)
FF_LIBRARY          = "F-F_Research_Data_5_Factors_2x3_daily"  # pandas_datareader key


# ============================================================
# BACKTEST SCENARIOS (Phase 6)
# ============================================================
BACKTEST_SCENARIOS = {
    "GFC_2008":    ("2007-07-01", "2009-06-30"),
    "COVID_2020":  ("2019-10-01", "2021-03-31"),
    "MIDEAST_2026":("2025-10-01", None),           # None → use today
}

BACKTEST_INITIAL_CAPITAL = 1_000_000   # USD / KRW handled per asset in engine.py
BACKTEST_COMMISSION      = 0.001       # 0.1 % per trade


# ============================================================
# EVALUATION METRICS (Phase 7)
# ============================================================
ULCER_WINDOW        = 14              # rolling window for Ulcer Index
CALMAR_WINDOW       = 36             # months for Calmar Ratio calculation