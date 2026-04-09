# -*- coding: utf-8 -*-
import time
import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
import unicodedata
from config import CSV_ENCODING, TICKER_NORM, US_TICKERS

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
    """
    [Stage 2] 하이브리드 수집기: 한국(FDR) + 미국(yf Chunking) 통합
    """
    kr_tickers = [t for t in ticker_list if t.endswith('-KS') or t.endswith('-KQ')]
    us_tickers = [t for t in ticker_list if t not in kr_tickers]

    all_prices = []
    all_volumes = []

    # 1. 🇰🇷 한국 종목 수집 (FinanceDataReader - 빠르고 정확함)
    print(f"🇰🇷 Fetching {len(kr_tickers)} KRX assets via FDR...")
    for ticker in kr_tickers:
        try:
            clean_code = ticker.split('-')[0]
            df = fdr.DataReader(clean_code, start_date, end_date)
            if not df.empty:
                # 컬럼명을 yfinance와 맞추기 위해 티커명으로 변경
                price_ser = df['Close'].rename(clean_code)
                vol_ser = df['Volume'].rename(clean_code)
                all_prices.append(price_ser)
                all_volumes.append(vol_ser)
        except Exception as e:
            print(f"⚠️ KR Ticker {ticker} failed: {e}")

    # 2. 🇺🇸 미국 종목 수집 (yfinance - 청킹 & 슬립 적용)
    print(f"🇺🇸 Fetching {len(us_tickers)} US assets via yfinance (Chunks of {chunk_size})...")
    for i in range(0, len(us_tickers), chunk_size):
        chunk = us_tickers[i:i + chunk_size]
        try:
            data = yf.download(chunk, start=start_date, end=end_date, auto_adjust=True, progress=False)
            if not data.empty:
                all_prices.append(data['Close'])
                all_volumes.append(data['Volume'])
            time.sleep(1.5) # 야후 형님 눈치 보기
        except Exception as e:
            print(f"⚠️ US Chunk starting {chunk[0]} failed: {e}")

    # 3. 데이터 통합
    full_prices = pd.concat(all_prices, axis=1)
    full_volumes = pd.concat(all_volumes, axis=1)
    
    # 중복 제거 및 날짜 정렬
    full_prices = full_prices.loc[:, ~full_prices.columns.duplicated()].sort_index()
    full_volumes = full_volumes.loc[:, ~full_volumes.columns.duplicated()].sort_index()

    return full_prices, full_volumes

def filter_candidates(prices, volumes, top_n=50):
    """유동성 상위 200개 중 6개월 모멘텀 상위 50개 선발"""
    all_tickers = prices.columns
    kr_tickers = [t for t in all_tickers if t.isdigit()]
    us_tickers = [t for t in all_tickers if not t.isdigit()]

    def get_scores(tickers):
        if not tickers: return pd.Series()
        p_sub = prices[tickers]
        v_sub = volumes[tickers]
        
        dollar_vol = p_sub * v_sub
        avg_vol = dollar_vol.tail(20).mean()
        liquid_idx = avg_vol.nlargest(min(100, len(tickers))).index
        
        mom = (p_sub[liquid_idx].iloc[-1] / p_sub[liquid_idx].iloc[-126]) - 1
        return mom

    print(f"Hybrid Selection: KR({len(kr_tickers)}), US({len(us_tickers)})")
    
    kr_scores = get_scores(kr_tickers)
    us_scores = get_scores(us_tickers)
    
    # 1. 각 시장별 고정 쿼터 (15개씩)
    selected_kr = kr_scores.nlargest(15).index.tolist()
    selected_us = us_scores.nlargest(15).index.tolist()
    
    # 2. 와일드카드 (나머지 중 상위 20개)
    remaining_scores = pd.concat([
        kr_scores.drop(selected_kr, errors='ignore'),
        us_scores.drop(selected_us, errors='ignore')
    ])
    wildcards = remaining_scores.nlargest(20).index.tolist()
    
    final_candidates = selected_kr + selected_us + wildcards
    
    print(f"✅ Selected 50: KR({len(selected_kr + [w for w in wildcards if w in kr_tickers])}), "
          f"US({len(selected_us + [w for w in wildcards if w in us_tickers])})")
    
    return final_candidates

def apply_currency_conversion(price_df):
    """
    Identifies US tickers and converts their prices to KRW.
    Ensures that volatility and drawdowns include the FX impact.
    """
    # 1. Fetch USD/KRW spot rate for the price_df timeline
    start_date = price_df.index.min()
    end_date = price_df.index.max()
    
    fx_data = yf.download("USDKRW=X", start=start_date, end=end_date, auto_adjust=True)['Close'].squeeze()
    
    # 2. Align FX dates with Price dates (handle holidays/weekends)
    fx_data = fx_data.reindex(price_df.index).ffill().bfill()
    
    # 3. Convert US-listed prices to KRW
    converted_df = price_df.copy()
    us_ticker_list = list(US_TICKERS.keys())
    
    for ticker in us_ticker_list:
        if ticker in converted_df.columns:
            # Price (KRW) = Price (USD) * FX (USD/KRW)
            converted_df[ticker] = converted_df[ticker] * fx_data
            
    return converted_df, fx_data