# -*- coding: utf-8 -*-
"""
portfolio/execution.py
=======================
Execution planner: consumes optimized weights and produces an order plan.

No alpha or risk logic. Responsibilities:
  - Check tradability vs liquidity caps
  - Convert weight targets to share/unit counts given NAV + prices
  - Generate a structured order DataFrame suitable for manual/broker review
"""

import numpy as np
import pandas as pd
import yfinance as yf
from portfolio.constraints import compute_liquidity_caps


def fetch_current_prices(tickers: list) -> pd.Series:
    """Fetches the most recent closing price for each ticker."""
    prices = {}
    for ticker in tickers:
        yf_ticker = f"{ticker}.KS" if (str(ticker)[0].isdigit() and not ticker.endswith(".KS")) else ticker
        try:
            df = yf.download(yf_ticker, period="3d", progress=False, auto_adjust=True)
            if not df.empty:
                close = df["Close"]
                if isinstance(close, pd.DataFrame):
                    close = close.iloc[:, 0]
                prices[ticker] = float(close.dropna().iloc[-1])
        except Exception:
            prices[ticker] = np.nan
    return pd.Series(prices)


def generate_order_plan(
    target_weights: pd.Series,
    current_weights: pd.Series | None,
    nav: float,
    volume_df: pd.DataFrame,
    price_df: pd.DataFrame,
    current_prices: pd.Series | None = None,
    participation_rate: float = 0.01,
    min_trade_threshold: float = 0.005,
) -> pd.DataFrame:
    """
    Generates an execution order plan.

    Parameters
    ----------
    target_weights      : new target allocation (normalized)
    current_weights     : existing allocation (None = flat/cash)
    nav                 : portfolio NAV in base currency
    volume_df           : historical daily volume (for liquidity check)
    price_df            : historical daily price (for liquidity check)
    current_prices      : latest prices (fetched if None)
    participation_rate  : fraction of ADV we are willing to trade in one day
    min_trade_threshold : skip trades below this weight delta

    Returns
    -------
    order_df : DataFrame with columns Ticker, Direction, Target_Weight,
               Current_Weight, Delta_Weight, Target_USD, Est_Shares,
               ADV_USD, Participation_Check
    """
    tickers = target_weights.index.tolist()

    if current_weights is None:
        current_weights = pd.Series(0.0, index=tickers)
    else:
        current_weights = current_weights.reindex(tickers).fillna(0.0)

    if current_prices is None:
        current_prices = fetch_current_prices(tickers)

    liq_caps = compute_liquidity_caps(
        volume_df.reindex(columns=tickers),
        price_df.reindex(columns=tickers),
        nav,
        participation_rate,
    )

    rows = []
    for ticker in tickers:
        t_w = float(target_weights.get(ticker, 0.0))
        c_w = float(current_weights.get(ticker, 0.0))
        delta = t_w - c_w

        if abs(delta) < min_trade_threshold:
            continue

        price     = float(current_prices.get(ticker, np.nan))
        target_usd = t_w * nav
        est_shares = target_usd / price if (np.isfinite(price) and price > 0) else np.nan

        adv_vol   = float(volume_df[ticker].tail(20).mean()) if ticker in volume_df.columns else np.nan
        adv_usd   = adv_vol * price if (np.isfinite(adv_vol) and np.isfinite(price)) else np.nan
        daily_cap = adv_usd * participation_rate if np.isfinite(adv_usd) else np.nan
        trade_usd = abs(delta) * nav
        ok        = bool(trade_usd <= daily_cap) if np.isfinite(daily_cap) else None

        rows.append({
            "Ticker":               ticker,
            "Direction":            "BUY" if delta > 0 else "SELL",
            "Target_Weight":        round(t_w, 5),
            "Current_Weight":       round(c_w, 5),
            "Delta_Weight":         round(delta, 5),
            "Target_USD":           round(target_usd, 2),
            "Est_Shares":           round(est_shares, 2) if np.isfinite(est_shares) else None,
            "Current_Price":        round(price, 4) if np.isfinite(price) else None,
            "ADV_USD":              round(adv_usd, 0) if np.isfinite(adv_usd) else None,
            "Participation_Check":  ok,
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=[
        "Ticker", "Direction", "Target_Weight", "Current_Weight",
        "Delta_Weight", "Target_USD", "Est_Shares", "Current_Price",
        "ADV_USD", "Participation_Check",
    ])
