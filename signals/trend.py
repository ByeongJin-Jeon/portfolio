# -*- coding: utf-8 -*-
"""
signals/trend.py  [LEGACY / RESEARCH ONLY]
==========================================
This module is NOT imported in the production pipeline.

Trend-based price signals (Minervini score, 6-month return ranking,
moving-average alignment) violate the "no past price trends as alpha"
design requirement and have been removed from the main path.

Retained only for:
  - Historical reference
  - Research / exploratory benchmarking
  - Comparison against the fundamental alpha model

DO NOT import from this module in main.py or signals/composer.py.
"""

import warnings
warnings.warn(
    "signals/trend.py is a legacy research-only module. "
    "Do not use in the production pipeline.",
    DeprecationWarning,
    stacklevel=2,
)

import numpy as np
import pandas as pd


def calculate_minervini_score(prices: pd.DataFrame, volumes: pd.DataFrame, ticker: str) -> float:
    """[LEGACY] 17-point Minervini VCP trend-template score. Returns 0-100."""
    try:
        p = prices[ticker].shift(1)  # prevent lookahead
        v = volumes[ticker].shift(1)
        if len(p.dropna()) < 252:
            return 0.0

        ma50  = p.rolling(50).mean()
        ma150 = p.rolling(150).mean()
        ma200 = p.rolling(200).mean()
        ma20  = p.rolling(20).mean()

        score = 0
        curr = p.iloc[-1]
        if curr > ma150.iloc[-1]: score += 1
        if curr > ma200.iloc[-1]: score += 1
        if ma150.iloc[-1] > ma200.iloc[-1]: score += 1
        if (ma200.diff(20) > 0).iloc[-1]: score += 1
        if ma50.iloc[-1] > ma150.iloc[-1]: score += 1
        if ma50.iloc[-1] > ma200.iloc[-1]: score += 1
        if curr > ma50.iloc[-1]: score += 1

        h52 = p.rolling(252).max().iloc[-1]
        l52 = p.rolling(252).min().iloc[-1]
        if curr > l52 * 1.30: score += 1
        if curr > h52 * 0.75: score += 1

        tr = (p.rolling(2).max() - p.rolling(2).min())
        atr10 = tr.rolling(10).mean().iloc[-1]
        atr50 = tr.rolling(50).mean().iloc[-1]
        if atr10 < atr50: score += 1

        ret = p.pct_change()
        if (v[ret > 0].rolling(20).mean().iloc[-1] >
                v[ret < 0].rolling(20).mean().iloc[-1]):
            score += 1
        if v.iloc[-1] > v.rolling(50).mean().iloc[-1]: score += 1

        band = (p.rolling(15).max() / p.rolling(15).min() - 1).iloc[-1]
        if band < 0.10: score += 1

        delta = p.diff()
        gain  = delta.where(delta > 0, 0.0).ewm(alpha=1/14, adjust=False).mean()
        loss  = (-delta.where(delta < 0, 0.0)).ewm(alpha=1/14, adjust=False).mean()
        rsi   = (100.0 - (100.0 / (1.0 + gain / (loss + 1e-9)))).iloc[-1]
        if rsi > 60: score += 1
        if curr > ma20.iloc[-1]: score += 1

        exp1 = p.ewm(span=12, adjust=False).mean()
        exp2 = p.ewm(span=26, adjust=False).mean()
        hist  = (exp1 - exp2) - (exp1 - exp2).ewm(span=9, adjust=False).mean()
        if hist.iloc[-1] > 0: score += 1

        return (score / 17.0) * 100.0
    except Exception:
        return 0.0


def generate_trend_views(prices: pd.DataFrame, volumes: pd.DataFrame) -> pd.Series:
    """[LEGACY] Trend-based views per ticker. NOT for production use."""
    tickers = prices.columns.tolist()
    scores = {t: calculate_minervini_score(prices, volumes, t) for t in tickers}
    s = pd.Series(scores)
    mn, mx = s.min(), s.max()
    return (s - mn) / (mx - mn) if mx > mn else pd.Series(0.5, index=s.index)
