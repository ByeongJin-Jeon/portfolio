# -*- coding: utf-8 -*-
"""
signals/options_skew.py
=======================
Options uncertainty penalty module.

Role: produce u_i uncertainty penalty per asset in annualized return units.
      u_i is consumed by: mu_tilde_i = mu_i - gamma_u * u_i - gamma_l * l_i

NOT a directional alpha source. Options-implied information is treated as
event-risk uncertainty, not as smart-money directional signal.

Output contract:
  build_uncertainty_penalty_vector(tickers) -> pd.Series of u_i (annualized decimal)
"""

import numpy as np
import pandas as pd
import yfinance as yf


def fetch_options_risk_snapshot(ticker: str) -> dict:
    """
    Fetches nearest-expiry options data for a single ticker.
    Returns dict with iv_skew, put_iv, call_iv, or None on failure.
    """
    try:
        t_obj = yf.Ticker(ticker)
        exps  = t_obj.options
        if not exps:
            return {}

        chain = t_obj.option_chain(exps[0])
        hist  = t_obj.history(period="1d")
        if hist.empty:
            return {}
        current_price = float(hist["Close"].iloc[-1])

        otm_calls = chain.calls[
            (chain.calls["strike"] > current_price) &
            (chain.calls["strike"] <= current_price * 1.10) &
            (chain.calls["volume"].fillna(0) > 0)
        ]
        otm_puts = chain.puts[
            (chain.puts["strike"] < current_price) &
            (chain.puts["strike"] >= current_price * 0.90) &
            (chain.puts["volume"].fillna(0) > 0)
        ]

        if otm_calls.empty or otm_puts.empty:
            return {}

        call_target = current_price * 1.05
        put_target  = current_price * 0.95

        closest_call = otm_calls.iloc[(otm_calls["strike"] - call_target).abs().argsort()[:1]]
        closest_put  = otm_puts.iloc[(otm_puts["strike"] - put_target).abs().argsort()[:1]]

        call_iv = float(closest_call["impliedVolatility"].values[0])
        put_iv  = float(closest_put["impliedVolatility"].values[0])

        avg_iv    = (call_iv + put_iv) / 2.0
        iv_skew   = put_iv - call_iv   # positive = elevated put demand (fear)

        return {
            "call_iv":   call_iv,
            "put_iv":    put_iv,
            "avg_iv":    avg_iv,
            "iv_skew":   iv_skew,
        }
    except Exception:
        return {}


def compute_event_risk_score(options_snapshot: dict) -> float:
    """
    Translates options snapshot into a scalar uncertainty score.
    Elevated put-call skew and high average IV both increase uncertainty.
    Returns value in [0, 1] (higher = more uncertain).
    """
    if not options_snapshot:
        return 0.5   # missing data -> neutral uncertainty

    avg_iv  = options_snapshot.get("avg_iv", 0.20)
    iv_skew = options_snapshot.get("iv_skew", 0.0)

    # IV component: annualized vol of 20% = 0 penalty; 50% = 1.0 penalty
    iv_component   = np.clip((avg_iv - 0.20) / 0.30, 0.0, 1.0)
    # Skew component: put-call skew of 0 = 0; 0.15+ = 1.0
    skew_component = np.clip(iv_skew / 0.15, 0.0, 1.0)

    return 0.6 * iv_component + 0.4 * skew_component


def build_uncertainty_penalty_vector(
    tickers: list,
    sigma_scale: float = 0.10,
) -> pd.Series:
    """
    Builds the u_i uncertainty penalty vector in annualized return units.

    u_i = event_risk_score_i * sigma_scale

    sigma_scale (default 0.10) represents the maximum annualized uncertainty
    penalty (10 bps per unit of composite sigma). This keeps u_i dimensionally
    consistent with mu_i (both in annualized decimal return units).

    KR tickers (digit-starting, no options on yfinance) receive the median
    score estimated from EWY/DRAM/KORU proxies.
    """
    proxy_tickers = ["EWY", "DRAM", "KORU"]
    proxy_scores  = []
    for pt in proxy_tickers:
        snap  = fetch_options_risk_snapshot(pt)
        score = compute_event_risk_score(snap)
        proxy_scores.append(score)
    kr_proxy_score = float(np.median(proxy_scores)) if proxy_scores else 0.5

    u_dict = {}
    for ticker in tickers:
        is_kr = str(ticker)[0].isdigit()
        if is_kr:
            u_dict[ticker] = kr_proxy_score * sigma_scale
        else:
            snap  = fetch_options_risk_snapshot(ticker)
            score = compute_event_risk_score(snap)
            u_dict[ticker] = score * sigma_scale

    return pd.Series(u_dict, name="u_penalty")
