# -*- coding: utf-8 -*-
"""
data/loader.py
==============
Market data loading and candidate frame construction.

Design rules:
- No trend-based eligibility filters
- No hard KR/US quota split
- ETF shelter assets pass eligibility automatically
- Currency tags flow from universe metadata, not post-hoc FX heuristics
"""

import time
import unicodedata
import numpy as np
import pandas as pd
import yfinance as yf
from config import (
    DATA_DIR, CSV_ENCODING, TICKER_NORM, PRICE_START, PRICE_END,
    ETF_SHELTER_TICKERS, MAX_PARTICIPATION_RATE, COVARIANCE_WINDOW,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def normalize_ticker_name(name: str) -> str:
    return unicodedata.normalize(TICKER_NORM, name) if isinstance(name, str) else name


def load_from_cache(name: str) -> pd.DataFrame | None:
    path = DATA_DIR / f"{name}"
    if path.exists():
        df = pd.read_csv(path, index_col=0, parse_dates=True, encoding=CSV_ENCODING)
        df.columns = [normalize_ticker_name(c) for c in df.columns]
        return df
    return None


def save_to_cache(df: pd.DataFrame, name: str) -> None:
    path = DATA_DIR / f"{name}"
    df.to_csv(path, encoding=CSV_ENCODING)


# ── data fetching ─────────────────────────────────────────────────────────────

def fetch_data_in_chunks(
    tickers: list,
    start_date: str = PRICE_START,
    end_date: str | None = PRICE_END,
    chunk_size: int = 50,
) -> dict[str, pd.DataFrame]:
    """
    Downloads Close and Volume in chunks of chunk_size.
    Returns dict {"close": pd.DataFrame, "volume": pd.DataFrame}.
    KR tickers (digit-starting) are normalised to .KS suffix before download.
    """
    close_parts, volume_parts = [], []

    def _yf_ticker(t: str) -> str:
        if t[0].isdigit():
            code = t.split(".")[0].zfill(6)
            return f"{code}.KS"
        return t

    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i : i + chunk_size]
        yf_chunk = [_yf_ticker(t) for t in chunk]
        try:
            raw = yf.download(
                yf_chunk, start=start_date, end=end_date,
                auto_adjust=True, progress=False, threads=True,
            )
            if raw.empty:
                continue
            if isinstance(raw.columns, pd.MultiIndex):
                c = raw["Close"] if "Close" in raw else pd.DataFrame()
                v = raw["Volume"] if "Volume" in raw else pd.DataFrame()
            else:
                c = raw[["Close"]] if "Close" in raw else pd.DataFrame()
                v = raw[["Volume"]] if "Volume" in raw else pd.DataFrame()
            close_parts.append(c)
            volume_parts.append(v)
            time.sleep(0.5)
        except Exception:
            pass

    close_df  = pd.concat(close_parts, axis=1).sort_index() if close_parts else pd.DataFrame()
    volume_df = pd.concat(volume_parts, axis=1).sort_index() if volume_parts else pd.DataFrame()
    close_df  = close_df.loc[:, ~close_df.columns.duplicated()]
    volume_df = volume_df.loc[:, ~volume_df.columns.duplicated()]
    return {"close": close_df, "volume": volume_df}


def apply_currency_conversion(
    close_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Converts USD-denominated prices to KRW for unified portfolio accounting.
    Currency assignment comes from metadata_df, not ticker-name heuristics.
    Returns (converted_df, fx_series).
    """
    try:
        fx_raw = yf.download(
            "USDKRW=X",
            start=str(close_df.index[0].date()),
            end=str(close_df.index[-1].date()),
            auto_adjust=True, progress=False,
        )
        fx = fx_raw["Close"].reindex(close_df.index).ffill().bfill()
        if isinstance(fx, pd.DataFrame):
            fx = fx.iloc[:, 0]
    except Exception:
        fx = pd.Series(1300.0, index=close_df.index)

    converted = close_df.copy()
    for ticker in close_df.columns:
        currency = "USD"
        if ticker in metadata_df.index:
            currency = metadata_df.loc[ticker, "trading_currency"]
        if currency == "USD":
            converted[ticker] = close_df[ticker] * fx
    return converted, fx


# ── candidate frame construction ──────────────────────────────────────────────

def compute_adv(
    volume_df: pd.DataFrame,
    close_df: pd.DataFrame,
    window: int = 20,
) -> pd.Series:
    """Average daily traded value (price × volume) over rolling window."""
    aligned = close_df.reindex(volume_df.index).ffill()
    return (volume_df * aligned).tail(window).mean()


def compute_liquidity_caps(
    candidate_df: pd.DataFrame,
    nav: float,
    kappa: float = MAX_PARTICIPATION_RATE,
) -> pd.Series:
    """
    Per-asset weight cap = kappa * ADV / NAV.
    ETF shelter assets always receive cap = 1.0 (not liquidity-constrained).
    """
    caps = (kappa * candidate_df["adv"] / max(nav, 1.0)).clip(upper=1.0)
    for ticker in candidate_df.index:
        if candidate_df.loc[ticker, "is_etf_shelter"]:
            caps[ticker] = 1.0
    return caps


def apply_basic_eligibility(candidate_df: pd.DataFrame) -> pd.DataFrame:
    """
    Keeps assets that either:
      (a) are ETF shelter assets (always pass), or
      (b) have sufficient price history and positive ADV.

    No trend-based filters. No country-quota splits.
    """
    shelter = candidate_df["is_etf_shelter"] == True
    has_history = candidate_df["n_obs"] >= COVARIANCE_WINDOW
    has_volume  = candidate_df["adv"] > 0
    return candidate_df[shelter | (has_history & has_volume)].copy()


def build_candidate_frame(
    close_df: pd.DataFrame,
    volume_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Constructs the candidate DataFrame consumed by all downstream modules.

    Output columns:
        n_obs, adv, is_etf_shelter, country, trading_currency,
        instrument_type, sector, sleeve, is_defensive, is_safe_haven
    """
    adv   = compute_adv(volume_df, close_df)
    n_obs = close_df.notna().sum()

    rows = []
    for ticker in close_df.columns:
        if ticker in metadata_df.index:
            meta = metadata_df.loc[ticker]
            get = lambda k, d: meta[k] if k in meta.index else d
        else:
            meta = None
            get = lambda k, d: d

        rows.append({
            "ticker":           ticker,
            "n_obs":            int(n_obs.get(ticker, 0)),
            "adv":              float(adv.get(ticker, 0.0)),
            "is_etf_shelter":   bool(get("is_etf_shelter", False)),
            "country":          get("country", "US"),
            "trading_currency": get("trading_currency", "USD"),
            "instrument_type":  get("instrument_type", "equity"),
            "sector":           get("sector", "Unknown"),
            "sleeve":           get("sleeve", "global_equity"),
            "is_defensive":     bool(get("is_defensive", False)),
            "is_safe_haven":    bool(get("is_safe_haven", False)),
        })

    df = pd.DataFrame(rows).set_index("ticker")
    return apply_basic_eligibility(df)
