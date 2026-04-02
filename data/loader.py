# -*- coding: utf-8 -*-
import pandas as pd
import unicodedata
from config import CSV_ENCODING, TICKER_NORM

def normalize_ticker_name(name):
    """Applies NFC normalization to ensure Korean strings match across OS platforms."""
    return unicodedata.normalize(TICKER_NORM, name) if isinstance(name, str) else name

def save_to_cache(df, filename):
    """Saves price data using utf-8-sig to preserve Hangul."""
    df.to_csv(filename, encoding=CSV_ENCODING)

def load_from_cache(filename):
    """Loads price data and ensures ticker names are normalized."""
    df = pd.read_csv(filename, index_col=0, parse_dates=True, encoding=CSV_ENCODING)
    df.columns = [normalize_ticker_name(col) for col in df.columns]
    return df