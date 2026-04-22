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

for _dir in [DATA_DIR, OUTPUT_DIR]:
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
# CORE MACRO ETFs (Phase 0 — 생존용 근본 방어막)
# ============================================================
CORE_ETFS = [
    # 미국 매크로/섹터 방어막 (2008년 이전 상장 위주)
    "SPY",   # S&P 500 (시장 베타)
    "DBC",   # 원자재 (공급 충격 방어)
    "VNQ",   # 미국 리츠/부동산
    "XLK",   # 기술주 섹터
    "XLE",   # 에너지 섹터 (MIDEAST 시나리오 하드캐리)
    "XLV",   # 헬스케어 (방어주)
    
    # 한국 매크로 방어막 (그나마 역사 긴 놈들)
    "069500", # KODEX 200 (한국 시장 베타, 2002년 상장)
    "139260", # TIGER 200 IT (한국 반도체/IT 베타)
]

DEFENSIVE_ETFS = [
    # 미국 찐 방어막
    "TLT",   # 미국 장기 국채
    "IEF",   # 미국 중기 국채
    "SHV",   # 미국 단기채 (초안전)
    "SGOV",  # 달러 현금성
    "GLD",   # 금
    # 한국 찐 방어막
    "114260", # KODEX 국고채3년
    "148070", # KOEF 국고채10년 (혹시 몰라 추가)
    "456880", # ACE SOFR ETF (달러 파킹)
]

# ============================================================
# SIGNAL PARAMETERS (Phase 1-A — Trend)
# ============================================================
MA_PERIODS     = [5, 22, 60, 182]    # short → long moving average windows
ENVELOPE_PERIOD = 22                  # central MA for the envelope
ENVELOPE_BAND   = 0.20                # ±10 % bands around the 22-day MA

# Minimum alignment score to generate a BL view (0.0 – 1.0)
# Signals below this gate are excluded from the Omega matrix entirely
MIN_SIGNAL_STRENGTH = 0.25            # i.e., at least 1 of 4 MA conditions met


# ============================================================
# MACRO RISK FILTERS (Phase 1-B — McGee TAA)
# ============================================================
VIX_KILLSWITCH     = 30.0     # if VIX ≥ this, reduce equity beta
VIX_CONFIDENCE_BASE = 20.0    # VIX level at which the Omega scalar = 1.0
                               # above this, confidence linearly decays:
                               # scalar = 1 + max(0, (VIX - 20) / 20)
FX_KILLSWITCH_LIMIT = 0.05     # if fx_volatility ≥ this, move all assets to dollar

TIPS_TICKER         = "TIP"   # iShares TIPS Bond ETF as real-rate proxy
SOFR_SAFE_HAVEN     = "SGOV"  # rotate here during VIX kill-switch (US equiv)
                               # KRX equivalent: "ACE SOFR ETF" (229200.KS)

Q_WEIGHTS           = {
                        'trend': 0.2,
                        'fundamental': 0.4,
                        'alpha': 0.2,
                        'skew': 0.2
                      }


# ============================================================
# ASSET UNIVERSE (Phase 3 — Multi-Asset Barbell Strategy)
# ============================================================
# Segment mapping for HRP risk-block clustering
SEGMENT_MAP = {
    # KRX
    "012450.KS": "Defense",
    "079550.KS": "Defense",
    "329180.KS": "Energy",
    "010130.KS": "SafeHaven",
    "005930.KS": "Core",
    "148070.KS": "Bond",
    "229200.KS": "Cash",
    
    # US
    "MSFT":      "Quality",
    "AAPL":      "Quality",
    "OXY":       "Energy",
    "ADM":       "Agri",
    "CTVA":      "Agri",
    "GLD":       "SafeHaven",
    "DBC":       "Commodity",
    "NEM":       "SafeHaven",
    "GOLD":      "SafeHaven",
    "JNJ":       "Core",
    "PG":        "Core",
    "TLT":       "Bond",
    "IEF":       "Bond",
    "SGOV":      "Cash",
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
RM_METHOD           = "CVaR"          # In Riskfolio, 'Sharpe' + 'rm' maximizes the Ulcer Performance Index

# CDaR / UPI
CDAR_ALPHA          = 0.05            # CVaR / CDaR confidence level
CDAR_LIMIT          = 0.15            # hard constraint: CDaR ≤ 15 %
RISK_FREE_RATE      = 0.04            # annualized (used in UPI & Calmar)


# ============================================================
# PORTFOLIO CONSTRAINTS (Phase 5)
# ============================================================
MAX_ASSETS          = 10              # final portfolio: top-N by weight
MIN_WEIGHT          = 0.01            # floor: 1 % per asset
MAX_WEIGHT_SINGLE   = 0.50            # ceiling: 30 % per asset
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