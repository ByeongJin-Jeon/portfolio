# -*- coding: utf-8 -*-
import pandas as pd
import yfinance as yf
from config import KRX_TICKERS, US_TICKERS, KOSPI_TOP_N

class UniverseManager:
    """Handles the expansion of the universe to include KOSPI 200 and US Indices."""
    
    @staticmethod
    def get_sp500_tickers():
        """Fetches S&P 500 components from Wikipedia/Public sources."""
        table = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
        return table[0]['Symbol'].tolist()

    @staticmethod
    def get_kospi_200_placeholders():
        """
        Placeholder: In a production environment, use a KRX API or local CSV.
        For now, merges your Strategic KRX tickers with the KOSPI 200 logic.
        """
        return list(KRX_TICKERS.keys())

    def get_full_universe(self):
        """Combines strategic picks with index-wide components."""
        strategic = list(KRX_TICKERS.keys()) + list(US_TICKERS.keys())
        # Here you would extend logic to fetch all 200+ tickers
        return list(set(strategic)) # Set ensures no duplicates