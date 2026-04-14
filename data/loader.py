# -*- coding: utf-8 -*-
import time
import pandas as pd
import numpy as np
import yfinance as yf
import urllib.request
import re
import FinanceDataReader as fdr
import unicodedata
from config import CSV_ENCODING, TICKER_NORM, US_TICKERS, CORE_ETFS

def is_kr_ticker(ticker):
    """
    한국 종목은 '무조건' 첫 글자가 숫자(0~9)로 시작함.
    미국 종목은 알파벳으로 시작함.
    """
    return str(ticker)[0].isdigit()

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

def fetch_data_in_chunks(ticker_list, start_date, end_date, chunk_size=50):
    """하이브리드 수집기: 한국(FDR) + 미국(yf Chunking) 통합"""
    kr_tickers = [t for t in ticker_list if is_kr_ticker(t)]
    us_tickers = [t for t in ticker_list if not is_kr_ticker(t)]

    all_prices = []
    all_volumes = []

    print(f"🇰🇷 Fetching {len(kr_tickers)} KRX assets via yfinance (Chunks of {chunk_size})...")
    
    kr_mapping = {}
    kr_yf_tickers = []

    for t in kr_tickers:
        clean_code = t.split('-')[0]
        yf_code = f"{clean_code}.KS"
        kr_mapping[yf_code] = clean_code
        kr_yf_tickers.append(yf_code)

    for i in range(0, len(kr_yf_tickers), chunk_size):
        chunk = kr_yf_tickers[i:i + chunk_size]
        try:
            data = yf.download(chunk, start=start_date, end=end_date, auto_adjust=True, progress=False)
            if not data.empty:
                price_df = data['Close']
                vol_df = data['Volume']
                
                if isinstance(price_df, pd.Series):
                    price_df = price_df.to_frame(name=chunk[0])
                    vol_df = vol_df.to_frame(name=chunk[0])
                
                price_df = price_df.rename(columns=kr_mapping)
                vol_df = vol_df.rename(columns=kr_mapping)
                
                all_prices.append(price_df)
                all_volumes.append(vol_df)
            time.sleep(1.5)
        except Exception as e:
            print(f"⚠️ KR Chunk starting {chunk[0]} failed: {e}")

    print(f"🇺🇸 Fetching {len(us_tickers)} US assets via yfinance (Chunks of {chunk_size})...")
    for i in range(0, len(us_tickers), chunk_size):
        chunk = us_tickers[i:i + chunk_size]
        try:
            data = yf.download(chunk, start=start_date, end=end_date, auto_adjust=True, progress=False)
            if not data.empty:
                all_prices.append(data['Close'])
                all_volumes.append(data['Volume'])
            time.sleep(1.5)
        except Exception as e:
            print(f"⚠️ US Chunk starting {chunk[0]} failed: {e}")

    full_prices = pd.concat(all_prices, axis=1)
    full_volumes = pd.concat(all_volumes, axis=1)
    
    full_prices = full_prices.loc[:, ~full_prices.columns.duplicated()].sort_index()
    full_volumes = full_volumes.loc[:, ~full_volumes.columns.duplicated()].sort_index()

    return full_prices, full_volumes

def get_naver_pbr(ticker):
    """
    야후 파이낸스가 버린 한국 종목 PBR을 네이버 금융에서 직접 긁어옴
    """
    clean_ticker = "".join([c for c in str(ticker) if c.isdigit()])
    clean_ticker = clean_ticker.zfill(6)

    url = f"https://finance.naver.com/item/main.naver?code={clean_ticker}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            html = response.read().decode('euc-kr', errors='ignore')
            
            match = re.search(r'id="_pbr">([\d\.]+)</em>', html)
            if match:
                return float(match.group(1))
            
            match_b = re.search(r'PBR.*?<em>([\d\.]+)</em>', html, re.DOTALL)
            if match_b:
                return float(match_b.group(1))
    except Exception as e:
        print(f"⚠️ Naver PBR scrape failed for {ticker}: {e}")
        
    return np.nan

def fetch_pbr_data(ticker_list):
    """Get the latest PBR data"""
    print("🔍 Fetching PBR data for candidates...")
    pbr_map = {}
    
    kr_tickers = [t for t in ticker_list if is_kr_ticker(t)]
    us_tickers = [t for t in ticker_list if not is_kr_ticker(t)]

    for t in kr_tickers:
        pbr = get_naver_pbr(t)
        pbr_map[t] = pbr

    for t in us_tickers:
        try:
            ticker_obj = yf.Ticker(t)
            pbr = ticker_obj.info.get('priceToBook', np.nan)
            pbr_map[t] = pbr
        except Exception as e:
            pbr_map[t] = np.nan
    
    return pd.Series(pbr_map)

def filter_candidates(price_df, volume_df):
    """6M 유동성 + Sharpe 모멘텀 + 저변동성 필터"""
    window = min(60, len(price_df) - 1)
    if window > 0:
        returns = price_df.ffill().pct_change(fill_method=None).tail(window)
        volatility = returns.std()
        volatility = volatility.replace(0, 0.0001)
        
        momentum = (price_df.iloc[-1] / price_df.iloc[-(window+1)]) - 1
        
        quality_score = momentum / volatility
    else:
        quality_score = pd.Series(1, index=price_df.columns)

    avg_volume = volume_df.tail(20).mean()
    avg_price = price_df.tail(20).mean()
    dollar_volume = avg_volume * avg_price

    is_kr = pd.Series(dollar_volume.index.map(is_kr_ticker), index=dollar_volume.index)
    kr_universe = dollar_volume[is_kr]
    us_universe = dollar_volume[~is_kr]

    top_kr_liquid = kr_universe.nlargest(50).index
    top_us_liquid = us_universe.nlargest(50).index

    selected_kr = quality_score.reindex(top_kr_liquid).nlargest(15).index.tolist()
    selected_us = quality_score.reindex(top_us_liquid).nlargest(15).index.tolist()

    remaining_liquid = list(set(top_kr_liquid.tolist() + top_us_liquid.tolist()) - set(selected_kr + selected_us))
    wildcards = quality_score.reindex(remaining_liquid).nlargest(20).index.tolist()

    final_50 = selected_kr + selected_us + wildcards

    final_list = list(set(final_50 + CORE_ETFS))
    final_list = [t for t in final_list if t in price_df.columns]

    print(f"✅ Selected {len(final_list)}: KR({len([t for t in final_50 if is_kr_ticker(t)])}), "
          f"US({len([t for t in final_50 if not is_kr_ticker(t)])}), "
          f"(Including {len(CORE_ETFS)} Core ETFs!)")
    
    return final_list

def apply_currency_conversion(price_df):
    """
    Identifies US tickers and converts their prices to KRW.
    Ensures that volatility and drawdowns include the FX impact.
    """
    start_date = price_df.index.min()
    end_date = price_df.index.max()
    
    fx_data = yf.download("USDKRW=X", start=start_date, end=end_date, auto_adjust=True)['Close'].squeeze()
    
    fx_data = fx_data.reindex(price_df.index).ffill().bfill()
    
    converted_df = price_df.copy()
    for ticker in converted_df.columns:
        if not str(ticker)[0].isdigit():
            converted_df[ticker] = converted_df[ticker] * fx_data
            
    return converted_df, fx_data