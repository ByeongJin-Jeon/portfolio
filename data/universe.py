# -*- coding: utf-8 -*-
"""
data/universe.py
================
Builds the metadata-rich universe DataFrame used by all downstream layers.

Every asset carries:
  ticker, country, trading_currency, instrument_type, sector, sleeve,
  is_etf_shelter, is_defensive, is_safe_haven

ETF shelter assets are flagged here and excluded from fundamental alpha scoring.
Individual equity assets flow into the fundamental alpha model.
"""

import pandas as pd
import FinanceDataReader as fdr
from urllib import request
from config import ETF_SHELTER_TICKERS

# ── hard-coded metadata for known ETF assets ─────────────────────────────────

_ETF_METADATA = {
    "TLT":        {"country": "US", "trading_currency": "USD", "instrument_type": "etf_bond",      "sector": "Bond",        "sleeve": "safe_haven_bond",      "is_defensive": True,  "is_safe_haven": True},
    "IEF":        {"country": "US", "trading_currency": "USD", "instrument_type": "etf_bond",      "sector": "Bond",        "sleeve": "safe_haven_bond",      "is_defensive": True,  "is_safe_haven": True},
    "SHV":        {"country": "US", "trading_currency": "USD", "instrument_type": "etf_bond",      "sector": "Bond",        "sleeve": "safe_haven_bond",      "is_defensive": True,  "is_safe_haven": True},
    "SGOV":       {"country": "US", "trading_currency": "USD", "instrument_type": "etf_cash",      "sector": "Cash",        "sleeve": "cash",                 "is_defensive": True,  "is_safe_haven": True},
    "GLD":        {"country": "US", "trading_currency": "USD", "instrument_type": "etf_commodity", "sector": "Commodity",   "sleeve": "safe_haven_commodity", "is_defensive": True,  "is_safe_haven": True},
    "DBC":        {"country": "US", "trading_currency": "USD", "instrument_type": "etf_commodity", "sector": "Commodity",   "sleeve": "commodity",            "is_defensive": False, "is_safe_haven": False},
    "SPY":        {"country": "US", "trading_currency": "USD", "instrument_type": "etf_index",     "sector": "Equity",      "sleeve": "equity_index",         "is_defensive": False, "is_safe_haven": False},
    "VNQ":        {"country": "US", "trading_currency": "USD", "instrument_type": "etf_index",     "sector": "RealEstate",  "sleeve": "equity_index",         "is_defensive": False, "is_safe_haven": False},
    "XLK":        {"country": "US", "trading_currency": "USD", "instrument_type": "etf_index",     "sector": "Technology",  "sleeve": "equity_index",         "is_defensive": False, "is_safe_haven": False},
    "XLE":        {"country": "US", "trading_currency": "USD", "instrument_type": "etf_index",     "sector": "Energy",      "sleeve": "equity_index",         "is_defensive": False, "is_safe_haven": False},
    "XLV":        {"country": "US", "trading_currency": "USD", "instrument_type": "etf_index",     "sector": "Healthcare",  "sleeve": "equity_index",         "is_defensive": False, "is_safe_haven": False},
    "114260.KS":  {"country": "KR", "trading_currency": "KRW", "instrument_type": "etf_bond",      "sector": "Bond",        "sleeve": "safe_haven_bond",      "is_defensive": True,  "is_safe_haven": True},
    "148070.KS":  {"country": "KR", "trading_currency": "KRW", "instrument_type": "etf_bond",      "sector": "Bond",        "sleeve": "safe_haven_bond",      "is_defensive": True,  "is_safe_haven": True},
    "456880.KS":  {"country": "KR", "trading_currency": "KRW", "instrument_type": "etf_cash",      "sector": "Cash",        "sleeve": "cash",                 "is_defensive": True,  "is_safe_haven": True},
    "069500.KS":  {"country": "KR", "trading_currency": "KRW", "instrument_type": "etf_index",     "sector": "Equity",      "sleeve": "equity_index",         "is_defensive": False, "is_safe_haven": False},
    "139260.KS":  {"country": "KR", "trading_currency": "KRW", "instrument_type": "etf_index",     "sector": "Technology",  "sleeve": "equity_index",         "is_defensive": False, "is_safe_haven": False},
}

_EQUITY_SECTOR_OVERRIDES = {
    "005930.KS": "Technology",
    "012450.KS": "Industrials",
    "079550.KS": "Industrials",
    "329180.KS": "Energy",
    "010130.KS": "Materials",
    "MSFT": "Technology",
    "AAPL": "Technology",
    "OXY":  "Energy",
    "ADM":  "ConsumerStaples",
    "CTVA": "Materials",
    "NEM":  "Materials",
    "GOLD": "Materials",
    "JNJ":  "Healthcare",
    "PG":   "ConsumerStaples",
}


def is_etf_shelter(ticker: str) -> bool:
    return ticker in ETF_SHELTER_TICKERS


def classify_instrument_type(ticker: str) -> str:
    if ticker in _ETF_METADATA:
        return _ETF_METADATA[ticker]["instrument_type"]
    return "equity"


def assign_sleeve(ticker: str) -> str:
    if ticker in _ETF_METADATA:
        return _ETF_METADATA[ticker]["sleeve"]
    return "global_equity"


def _equity_row(ticker: str) -> dict:
    country  = "KR" if (".KS" in ticker or ".KQ" in ticker) else "US"
    currency = "KRW" if country == "KR" else "USD"
    sector   = _EQUITY_SECTOR_OVERRIDES.get(ticker, "Unknown")
    return {
        "ticker":           ticker,
        "country":          country,
        "trading_currency": currency,
        "instrument_type":  "equity",
        "sector":           sector,
        "sleeve":           "global_equity",
        "is_etf_shelter":   False,
        "is_defensive":     False,
        "is_safe_haven":    False,
    }


def _etf_row(ticker: str) -> dict:
    meta = _ETF_METADATA.get(ticker, {})
    return {
        "ticker":           ticker,
        "country":          meta.get("country", "US"),
        "trading_currency": meta.get("trading_currency", "USD"),
        "instrument_type":  meta.get("instrument_type", "etf_index"),
        "sector":           meta.get("sector", "Unknown"),
        "sleeve":           meta.get("sleeve", "equity_index"),
        "is_etf_shelter":   ticker in ETF_SHELTER_TICKERS,
        "is_defensive":     meta.get("is_defensive", False),
        "is_safe_haven":    meta.get("is_safe_haven", False),
    }


class UniverseManager:

    @staticmethod
    def get_sp500_tickers() -> list:
        try:
            url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
            req = request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with request.urlopen(req) as resp:
                table = pd.read_html(resp)[0]
            return table["Symbol"].str.replace(".", "-", regex=False).tolist()
        except Exception:
            return []

    @staticmethod
    def get_nasdaq100_tickers() -> list:
        try:
            url = "https://en.wikipedia.org/wiki/Nasdaq-100"
            req = request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with request.urlopen(req) as resp:
                tables = pd.read_html(resp)
            for t in tables:
                if "Ticker" in t.columns:
                    return t["Ticker"].str.replace(".", "-", regex=False).tolist()
            return []
        except Exception:
            return []

    @staticmethod
    def get_dow_jones_tickers() -> list:
        try:
            url = "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average"
            req = request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with request.urlopen(req) as resp:
                table = pd.read_html(resp)[1]
            return table["Symbol"].str.replace(".", "-", regex=False).tolist()
        except Exception:
            return []

    @staticmethod
    def get_kospi_200_tickers() -> list:
        try:
            df = fdr.StockListing("KOSPI")
            return [f"{code}.KS" for code in df["Code"].head(200).tolist()]
        except Exception:
            return []

    def get_full_universe(self) -> list:
        tickers: set = set()
        for method in [
            self.get_sp500_tickers,
            self.get_nasdaq100_tickers,
            self.get_dow_jones_tickers,
            self.get_kospi_200_tickers,
        ]:
            try:
                tickers.update(method())
            except Exception:
                pass
        tickers.update(ETF_SHELTER_TICKERS)
        return sorted(tickers)

    def get_universe_metadata(self) -> pd.DataFrame:
        """
        Returns a DataFrame with one row per asset.
        Schema: country, trading_currency, instrument_type, sector, sleeve,
                is_etf_shelter, is_defensive, is_safe_haven.
        This is the single metadata contract used by all downstream modules.
        """
        rows = []
        for ticker in self.get_full_universe():
            if ticker in _ETF_METADATA or ticker in ETF_SHELTER_TICKERS:
                rows.append(_etf_row(ticker))
            else:
                rows.append(_equity_row(ticker))
        df = pd.DataFrame(rows).set_index("ticker")
        return df
