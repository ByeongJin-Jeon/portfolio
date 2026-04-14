# -*- coding: utf-8 -*-
import pandas as pd
import yfinance as yf
import numpy as np

def is_kr_ticker(ticker):
    return str(ticker)[0].isdigit()

def generate_fundamental_views(tickers):
    """
    Bet on the upside or downside based on EPS upward adjustment (Earnings Momentum) and FCF Yield
    """    
    views = pd.Series(0.0, index=tickers)
    
    for ticker in tickers:
        try:
            yf_ticker = ticker
            if is_kr_ticker(ticker):
                if not ticker.endswith('.KS') and not ticker.endswith('.KQ'):
                    yf_ticker = f"{ticker}.KS"
            
            stock = yf.Ticker(yf_ticker)
            info = stock.info
            
            if info.get('quoteType') == 'ETF':
                continue
            
            score = 0.0
            
            # 1. FCF Yield
            fcf = info.get('freeCashflow', 0)
            ev = info.get('enterpriseValue', 0)
            if ev > 0 and fcf > 0:
                fcf_yield = fcf / ev
                if fcf_yield > 0.05:
                    score += 1.0
            
            # 2. Earning momentum (short-term upside)
            try:
                eps_trend = stock.eps_revisions if hasattr(stock, 'eps_revisions') else None
                if eps_trend is not None and isinstance(eps_trend, dict):
                    up_revisions = eps_trend.get('upLast30days', 0)
                    down_revisions = eps_trend.get('downLast30days', 0)
                    
                    if up_revisions > down_revisions:
                        score += 1.5
                    elif down_revisions > up_revisions:
                        score -= 1.0
            except Exception:
                pass
                
            views[ticker] = score
            
        except Exception as e:
            views[ticker] = 0.0
            
    # View normalization
    max_score = views.abs().max()
    if max_score > 0:
        views = views / max_score
        
    return views