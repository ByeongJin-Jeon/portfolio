# -*- coding: utf-8 -*-
import pandas as pd
import yfinance as yf
import numpy as np
import requests
import io

def is_kr_ticker(ticker):
    return str(ticker)[0].isdigit()

def get_kr_operating_profit(clean_ticker):
    """Crawling the most recent fiscal year's FCF from Naver Finance"""
    url = f"https://finance.naver.com/item/main.naver?code={clean_ticker}"
    
    headers = {'User-Agent': 'Mozilla/5.0'}

    try:
        res = requests.get(url, headers=headers, timeout=5)
        html_io = io.StringIO(res.text)
        tables = pd.read_html(html_io, encoding='euc-kr', match='영업이익')
        
        if tables:
            df = tables[0]
            
            op_row = df[df.iloc[:, 0] == '영업이익']
            
            if not op_row.empty:
                recent_op = op_row.iloc[0, 3] 
                
                if pd.notna(recent_op):
                    clean_op = str(recent_op).replace(',', '')
                    if clean_op.replace('.', '', 1).replace('-', '', 1).isdigit():
                        return float(clean_op) * 100000000
    
    except Exception as e:
        print(f"Fail to crawling {clean_ticker} FCF data: {e}")
        pass

    return 0.0

def generate_fundamental_views(tickers):
    """
    Bet on the upside or downside based on EPS upward adjustment (Earnings Momentum) and FCF Yield
    """    
    views = pd.Series(0.0, index=tickers)
    score = 0.0
    
    for ticker in tickers:
        yf_ticker = ticker
        if is_kr_ticker(ticker):
            clean_ticker = str(ticker).replace('.KS', '').replace('.KQ', '')

            if clean_ticker in ["069500", "139260", "114260", "148070", "456880"]:
                continue
            
            op = get_kr_operating_profit(clean_ticker)
            
            stock = yf.Ticker(f"{clean_ticker}.KS")
            info = stock.info
            market_cap = info.get('marketCap', 0)
            
            if market_cap is not None and market_cap > 0 and op > 0:
                op_yield = op / market_cap
                if op_yield > 0.05:
                    score += 1.0
        else:
            stock = yf.Ticker(yf_ticker)
            info = stock.info
            
            if info.get('quoteType') == 'ETF':
                continue
            
            # 1. FCF Yield
            fcf = info.get('freeCashflow')
            ev = info.get('enterpriseValue')

            fcf = float(fcf) if fcf is not None else 0.0
            ev = float(ev) if ev is not None else 0.0
            
            if ev > 0 and fcf > 0:
                fcf_yield = fcf / ev
                if fcf_yield > 0.03:
                    score += 1.0
            
            # 2. Earning momentum (short-term upside)
            eps_trend = stock.eps_revisions if hasattr(stock, 'eps_revisions') else None

            # [PLAN A] If there exist eps revision from analysts!
            if eps_trend is not None and isinstance(eps_trend, dict) and 'upLast30days' in eps_trend:
                up_revisions = eps_trend.get('upLast30days', 0)
                down_revisions = eps_trend.get('downLast30days', 0)
                if up_revisions > down_revisions:
                    score += 1.5
                elif down_revisions > up_revisions:
                    score -= 1.0
            
            # [PLAN B] If there's no eps revision
            else:
                # earningsGrowth
                eg = info.get('earningsGrowth')
                
                # forwardEps vs trailingEps
                fwd_eps = info.get('forwardEps')
                trl_eps = info.get('trailingEps')
                
                # Earning grows over 10% or estimated next-year EPS is greater then this year
                if eg is not None and eg > 0.10:
                    score += 1.5
                elif (fwd_eps is not None and trl_eps is not None) and (fwd_eps > trl_eps * 1.05):
                    score += 1.0
                elif eg is not None and eg < -0.05:
                    score -= 1.0
            
        views[ticker] = score
            
    # View normalization
    max_score = views.abs().max()
    if max_score > 0:
        views = views / max_score
        
    return views