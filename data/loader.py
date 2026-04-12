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

def get_naver_pbr(ticker):
    """
    야후 파이낸스가 버린 한국 종목 PBR을 네이버 금융에서 직접 긁어옴
    """
    # 1. 00680K 같은 우선주 티커에서 알파벳 제거 (숫자 6자리만 추출)
    clean_ticker = "".join([c for c in str(ticker) if c.isdigit()])
    clean_ticker = clean_ticker.zfill(6) # 5930 -> 005930 포맷 맞추기

    url = f"https://finance.naver.com/item/main.naver?code={clean_ticker}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            html = response.read().decode('euc-kr', errors='ignore')
            
            # 네이버 금융 HTML에서 id="_pbr" 태그 안의 숫자만 쏙 빼오기
            match = re.search(r'id="_pbr">([\d\.]+)</em>', html)
            if match:
                return float(match.group(1))
            
            # 혹시 태그가 다를 경우를 대비한 플랜 B (PBR 글자 근처의 텍스트 탐색)
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

    # 1. 🇰🇷 한국 시장 소속 판별 (FDR을 '안내데스크'로 활용)
    for t in kr_tickers:
        pbr = get_naver_pbr(t)
        pbr_map[t] = pbr

    # 2. 🇺🇸 미국 PBR (yfinance)
    for t in us_tickers:
        try:
            ticker_obj = yf.Ticker(t)
            # info에서 가져오되, 없으면 nan
            pbr = ticker_obj.info.get('priceToBook', np.nan)
            pbr_map[t] = pbr
        except Exception as e:
            pbr_map[t] = np.nan
    
    return pd.Series(pbr_map)

def filter_candidates(price_df, volume_df, top_n=50):
    """6M 유동성 + Sharpe 모멘텀 + PBR 하방 필터 통합"""
    # 1. [핵심] 시차 때문에 생긴 빈칸(NaN)을 '가장 최근 장 열린 날의 가격'으로 채우기!
    filled_price = price_df.ffill()
    filled_volume = volume_df.ffill()
    
    # 거래대금 계산 (채워진 데이터로 공정하게!)
    dollar_volume = filled_price * filled_volume
    avg_vol = dollar_volume.tail(20).mean()
    
    # 2. 국가별 유동성 쿼터 (각각 50개씩 정예 선발)
    kr_pool = [t for t in avg_vol.index if is_kr_ticker(t)]
    us_pool = [t for t in avg_vol.index if not is_kr_ticker(t)]
    
    top_kr_liquid = avg_vol.reindex(kr_pool).nlargest(50).index
    top_us_liquid = avg_vol.reindex(us_pool).nlargest(50).index
    
    candidates_pool = top_kr_liquid.union(top_us_liquid)
    filtered_prices = filled_price[candidates_pool]
    
    # 3. 모멘텀 계산 (이제 빈칸이 없으니 억울한 실격자 제로!)
    returns_6m = filtered_prices.pct_change(126, fill_method=None).iloc[-1]
    volatility_6m = filtered_prices.pct_change(fill_method=None).tail(126).std() * np.sqrt(252)
    momentum_score = returns_6m / (volatility_6m + 1e-6)

    # 4. PBR 데이터 수집 및 점수화
    pbr_series = fetch_pbr_data(candidates_pool.tolist())
    pbr_series = pbr_series.reindex(candidates_pool).fillna(1.5) # 데이터 없으면 평범한 수준으로 가정
    value_score = 1 / pbr_series.clip(lower=0.1)

    # 5. 최종 점수 정규화 및 선발
    def z_score(s):
        return (s - s.mean()) / (s.std() + 1e-6)

    final_scores = (z_score(momentum_score) * 0.7) + (z_score(value_score) * 0.3)
    
    # [방어막 2] 혹시라도 점수가 NaN인 애들은 0점(평균)으로 메꿔서 실격 방지!
    final_scores = final_scores.fillna(0)
    
    selected_kr = final_scores.reindex(top_kr_liquid).nlargest(15).index.tolist()
    selected_us = final_scores.reindex(top_us_liquid).nlargest(15).index.tolist()
    
    remaining = final_scores.drop(selected_kr + selected_us, errors='ignore')
    wildcards = remaining.nlargest(20).index.tolist()
    
    final_50 = selected_kr + selected_us + wildcards
    final_list = list(set(final_50 + CORE_ETFS))
    final_list = [t for t in final_list if t in price_df.columns]
    
    print(f"✅ Selected {len(final_list)}: KR({len([t for t in final_50 if is_kr_ticker(t)])}), "
          f"US({len([t for t in final_50 if not is_kr_ticker(t)])}), "
          f"(Including Macro Core ETFs!)")
    
    return final_list

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
    for ticker in converted_df.columns:
        if not str(ticker)[0].isdigit():
            converted_df[ticker] = converted_df[ticker] * fx_data
            
    return converted_df, fx_data