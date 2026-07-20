# -*- coding: utf-8 -*-
"""
signals/macro.py
================
Macro risk governor — constraint modifier, NOT an alpha producer.

Role:
  - Classify the macro stress regime from VIX and FX volatility
  - Return constraint multipliers (sleeve floor adjustments, currency band tightening)
  - Do NOT produce per-asset expected return views

Output contract:
  get_macro_state()           -> dict {vix_level, fx_vol, stress_regime}
  build_constraint_multipliers() -> dict {sleeve_delta, ccy_delta}
  apply_macro_constraint_adjustments() -> adjusted constraint bounds
"""

import numpy as np
import pandas as pd
import yfinance as yf
import pandas_datareader.data as web
from config import (
    VIX_NORMAL_UPPER, VIX_ELEVATED_UPPER, FX_VOL_STRESS,
    SLEEVE_STRESS_DELTA, SLEEVE_DEFINITIONS,
)


def get_macro_state() -> dict:
    """
    Fetches current VIX and recent USDKRW volatility.
    Returns dict with keys: vix_level, fx_vol, stress_regime.

    stress_regime: one of {"normal", "elevated", "stress", "fx_stress"}
    Multiple regimes can be active simultaneously; the most severe is returned
    as the primary regime for constraint adjustment.
    """
    vix_level = 20.0
    fx_vol    = 0.0
    regimes   = []

    # VIX
    try:
        vix_raw = yf.download("^VIX", period="5d", auto_adjust=True, progress=False)["Close"]
        if isinstance(vix_raw, pd.DataFrame):
            vix_raw = vix_raw.iloc[:, 0]
        vix_level = float(vix_raw.dropna().iloc[-1])
    except Exception:
        pass

    # FX volatility (USDKRW 10-day range / midpoint)
    try:
        fx_raw = yf.download("USDKRW=X", period="15d", interval="1d", auto_adjust=True, progress=False)["Close"]
        if isinstance(fx_raw, pd.DataFrame):
            fx_raw = fx_raw.iloc[:, 0]
        recent = fx_raw.dropna().tail(10)
        if len(recent) >= 4:
            fx_vol = float((recent.max() - recent.min()) / recent.mean())
    except Exception:
        pass

    # Classify regimes
    if vix_level >= VIX_ELEVATED_UPPER:
        regimes.append("stress")
    elif vix_level >= VIX_NORMAL_UPPER:
        regimes.append("elevated")
    else:
        regimes.append("normal")

    if fx_vol >= FX_VOL_STRESS:
        regimes.append("fx_stress")

    # Primary regime: most severe
    severity = {"stress": 3, "fx_stress": 2, "elevated": 1, "normal": 0}
    primary  = max(regimes, key=lambda r: severity.get(r, 0))

    return {
        "vix_level":    vix_level,
        "fx_vol":       fx_vol,
        "stress_regime": primary,
        "active_regimes": regimes,
    }


def build_constraint_multipliers(macro_state: dict) -> dict:
    """
    Translates macro state into constraint adjustments.
    Returns a dict with:
      sleeve_delta : {sleeve_name: floor_increase}  — added to base sleeve minimums
      ccy_delta    : {ccy_pair: {min_delta, max_delta}}

    No per-asset expected return vector is produced.
    """
    active = macro_state.get("active_regimes", ["normal"])

    sleeve_delta: dict[str, float] = {}
    for regime in active:
        for sleeve, delta in SLEEVE_STRESS_DELTA.get(regime, {}).items():
            sleeve_delta[sleeve] = sleeve_delta.get(sleeve, 0.0) + delta

    ccy_delta: dict = {}
    if "fx_stress" in active:
        ccy_delta["KRW"] = {"max_delta": -0.05}   # tighten KRW cap
        ccy_delta["USD"] = {"min_delta": +0.05}    # raise USD floor
    if "stress" in active:
        ccy_delta.setdefault("KRW", {})["max_delta"] = ccy_delta.get("KRW", {}).get("max_delta", 0.0) - 0.05

    return {
        "sleeve_delta": sleeve_delta,
        "ccy_delta":    ccy_delta,
        "macro_state":  macro_state,
    }


def apply_macro_constraint_adjustments(
    base_sleeve_bounds: dict,
    base_ccy_bounds: dict,
    multipliers: dict,
) -> tuple[dict, dict]:
    """
    Applies the constraint multipliers from build_constraint_multipliers to
    the base sleeve and currency bounds.

    Parameters
    ----------
    base_sleeve_bounds : dict like {"safe_haven_bond": {"min": 0.05, "max": 0.40}, ...}
    base_ccy_bounds    : dict like {"KRW": {"min": 0.30, "max": 0.70}, ...}
    multipliers        : output of build_constraint_multipliers

    Returns
    -------
    adjusted_sleeve_bounds, adjusted_ccy_bounds
    """
    sleeve_delta = multipliers.get("sleeve_delta", {})
    ccy_delta    = multipliers.get("ccy_delta", {})

    adj_sleeve = {}
    for sleeve, bounds in base_sleeve_bounds.items():
        delta = sleeve_delta.get(sleeve, 0.0)
        adj_sleeve[sleeve] = {
            "min": min(bounds["min"] + delta, bounds["max"]),
            "max": bounds["max"],
        }

    adj_ccy = {}
    for ccy, bounds in base_ccy_bounds.items():
        d = ccy_delta.get(ccy, {})
        adj_ccy[ccy] = {
            "min": bounds["min"] + d.get("min_delta", 0.0),
            "max": bounds["max"] + d.get("max_delta", 0.0),
        }

    return adj_sleeve, adj_ccy
