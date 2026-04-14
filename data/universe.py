# data/universe.py

import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
from urllib import request
from config import KRX_TICKERS, US_TICKERS, CORE_ETFS

class UniverseManager:
    """S&P 500, Nasdaq 100, Dow Jones, KOSPI 200 요원들 싹 다 모아오기!"""
    
    @staticmethod
    def get_sp500_tickers():
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        req = request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with request.urlopen(req) as response:
            table = pd.read_html(response)
        return table[0]['Symbol'].tolist()

    @staticmethod
    def get_nasdaq100_tickers():
        url = 'https://en.wikipedia.org/wiki/Nasdaq-100'
        req = request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with request.urlopen(req) as response:
            table = pd.read_html(response)
        return table[4]['Ticker'].tolist()

    @staticmethod
    def get_dow_jones_tickers():
        url = 'https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average'
        req = request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with request.urlopen(req) as response:
            table = pd.read_html(response)
        return table[1]['Symbol'].tolist()

    @staticmethod
    def get_kospi_200_tickers():
        df = fdr.StockListing('KOSPI')
        kospi_200 = (df.head(200)['Code']).tolist()
        return kospi_200

    def get_full_universe(self):
        sp500 = self.get_sp500_tickers()
        nasdaq = self.get_nasdaq100_tickers()
        dow = self.get_dow_jones_tickers()
        kospi = self.get_kospi_200_tickers()
        # strategic_us = list(US_TICKERS.keys())
        
        full_list = list(set(sp500 + nasdaq + dow + kospi + CORE_ETFS))
        return [t.replace('.', '-') for t in full_list]