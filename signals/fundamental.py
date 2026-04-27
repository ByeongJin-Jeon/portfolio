# -*- coding: utf-8 -*-
import pandas as pd
import yfinance as yf
import numpy as np
import requests
import io
import time

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

def get_fundamental_data(ticker):
    """
    Fetches all necessary fundamental data for a given ticker.
    Returns a dictionary of dataframes/info.
    """
    try:
        yf_ticker = ticker
        if is_kr_ticker(ticker):
            clean_ticker = str(ticker).replace('.KS', '').replace('.KQ', '')
            yf_ticker = f"{clean_ticker}.KS"
        
        stock = yf.Ticker(yf_ticker)
        
        info = stock.info
        financials = stock.financials
        balancesheet = stock.balancesheet
        cashflow = stock.cashflow
        
        return {
            'info': info,
            'financials': financials,
            'balancesheet': balancesheet,
            'cashflow': cashflow
        }
    except Exception as e:
        print(f"   -> [WARNING] Error fetching fundamental data for {ticker}: {e}")
        return None

def score_custom_balance(data):
    """
    Custom Balance Scoring (16 points max -> 100 normalized)
    """
    if data is None or data['financials'].empty or data['balancesheet'].empty:
        return 0.0
    
    info = data['info']
    financials = data['financials']
    balancesheet = data['balancesheet']
    cashflow = data['cashflow']
    
    score = 0
    try:
        curr = financials.columns[0]
        prev = financials.columns[1] if len(financials.columns) > 1 else None
        
        bs_curr = balancesheet.columns[0]
        bs_prev = balancesheet.columns[1] if len(balancesheet.columns) > 1 else None
        
        cf_curr = cashflow.columns[0]
        
        # 1. Net Income > 0
        if financials.loc['Net Income', curr] > 0: score += 1
        
        # 2. CFO > 0
        cfo = cashflow.loc['Operating Cash Flow', cf_curr]
        if cfo > 0: score += 1
        
        # 3. FCF > 0
        fcf = info.get('freeCashflow', 0)
        if fcf is None: fcf = 0
        if fcf > 0: score += 1
        
        # 4. CFO > Net Income
        if cfo > financials.loc['Net Income', curr]: score += 1
        
        # 5. ROA > 0
        roa = info.get('returnOnAssets', 0)
        if roa is not None and roa > 0: score += 1
        
        # 6. Debt/Equity < 1.5
        de = info.get('debtToEquity', 0)
        if de is not None and de < 150: score += 1 
        
        # 7. Current Ratio > 1.2
        cr = info.get('currentRatio', 0)
        if cr is not None and cr > 1.2: score += 1
        
        # 8. Long-Term Debt < Net Working Capital
        nwc = balancesheet.loc['Current Assets', bs_curr] - balancesheet.loc['Current Liabilities', bs_curr]
        ltd = balancesheet.get('Long Term Debt', pd.Series(0, index=balancesheet.columns)).get(bs_curr, 0)
        if ltd < nwc: score += 1
        
        # 9. Interest Coverage > 3.0
        ebit = financials.loc['EBIT', curr]
        int_exp = abs(financials.get('Interest Expense', pd.Series(0, index=financials.columns)).get(curr, 0))
        if int_exp > 0 and (ebit / int_exp) > 3.0: score += 1
        elif int_exp == 0 and ebit > 0: score += 1
        
        if prev and bs_prev:
            # 10. YoY Total Debt Decrease
            curr_debt = balancesheet.get('Total Debt', pd.Series(0, index=balancesheet.columns)).get(bs_curr, 0)
            prev_debt = balancesheet.get('Total Debt', pd.Series(0, index=balancesheet.columns)).get(bs_prev, 0)
            if curr_debt < prev_debt: score += 1
            
            # 11. YoY Shares Outstanding Maintain/Decrease
            # Use current shares as proxy if historical not available
            score += 1 
            
            # 12. YoY Gross Margin Increase
            curr_gm = financials.loc['Gross Profit', curr] / financials.loc['Total Revenue', curr]
            prev_gm = financials.loc['Gross Profit', prev] / financials.loc['Total Revenue', prev]
            if curr_gm > prev_gm: score += 1
            
            # 13. YoY Asset Turnover Increase
            curr_at = financials.loc['Total Revenue', curr] / balancesheet.loc['Total Assets', bs_curr]
            prev_at = financials.loc['Total Revenue', prev] / balancesheet.loc['Total Assets', bs_prev]
            if curr_at > prev_at: score += 1
            
            # 14. YoY Inventory Turnover Increase
            if 'Inventory' in balancesheet.index and 'Cost Of Revenue' in financials.index:
                curr_it = abs(financials.loc['Cost Of Revenue', curr]) / balancesheet.loc['Inventory', bs_curr]
                prev_it = abs(financials.loc['Cost Of Revenue', prev]) / balancesheet.loc['Inventory', bs_prev]
                if curr_it > prev_it: score += 1
            else: score += 1
                
            # 15. YoY ROIC Increase
            def get_roic(f_date, b_date):
                ni = financials.loc['Net Income', f_date]
                debt = balancesheet.get('Total Debt', pd.Series(0, index=balancesheet.columns)).get(b_date, 0)
                equity = balancesheet.loc['Stockholders Equity', b_date]
                return ni / (debt + equity) if (debt + equity) != 0 else 0
            if get_roic(curr, bs_curr) > get_roic(prev, bs_prev): score += 1
        
        # 16. CapEx < CFO
        capex = abs(cashflow.get('Capital Expenditure', pd.Series(0, index=cashflow.columns)).get(cf_curr, 0))
        if capex < cfo: score += 1
        
    except Exception: pass
    return (score / 16.0) * 100.0

def score_custom_growth(data):
    """
    Custom Growth Scoring (11 points max -> 100 normalized)
    """
    if data is None or data['financials'].empty:
        return 0.0
    
    info = data['info']
    financials = data['financials']
    
    score = 0
    try:
        curr = financials.columns[0]
        prev = financials.columns[1] if len(financials.columns) > 1 else None
        
        # 1. Revenue YoY > 0
        if prev and financials.loc['Total Revenue', curr] > financials.loc['Total Revenue', prev]: score += 1
        # 2. Op Income YoY > 0
        if prev and financials.loc['Operating Income', curr] > financials.loc['Operating Income', prev]: score += 1
        # 3. EPS YoY > 0
        if prev and financials.loc['Net Income', curr] > financials.loc['Net Income', prev]: score += 1
        
        # 4 & 5. 3Y CAGR > 5%
        if len(financials.columns) >= 4:
            oldest = financials.columns[3]
            
            # Revenue CAGR (Revenue is almost always positive)
            rev_curr = financials.loc['Total Revenue', curr]
            rev_old = financials.loc['Total Revenue', oldest]
            if rev_curr > 0 and rev_old > 0:
                rev_cagr = (rev_curr / rev_old)**(1/3) - 1
                if rev_cagr > 0.05: score += 1
            elif rev_curr > rev_old: # Fallback for edge cases
                score += 1

            # Net Income CAGR (Handle negative values)
            ni_curr = financials.loc['Net Income', curr]
            ni_old = financials.loc['Net Income', oldest]
            
            if ni_curr > 0 and ni_old > 0:
                # Standard CAGR for positive growth
                ni_cagr = (ni_curr / ni_old)**(1/3) - 1
                if ni_cagr > 0.05: score += 1
            elif ni_curr > ni_old:
                # If it went from Loss -> Profit or Smaller Loss -> Larger Profit, it's growth
                score += 1
            
        # 6. Fwd EPS > Trl EPS
        fwd_eps = info.get('forwardEps')
        trl_eps = info.get('trailingEps')
        if fwd_eps and trl_eps and fwd_eps > trl_eps: score += 1
        
        # 7. upLast30days > downLast30days
        # 8. upLast30days >= 3
        up = info.get('earningsRevisionsUpLast30Days', 0)
        down = info.get('earningsRevisionsDownLast30Days', 0)
        if up is None: up = 0
        if down is None: down = 0
        if up > down: score += 1
        if up >= 3: score += 1
        
        # 9. Target Price > Current Price * 1.10
        cp = info.get('currentPrice')
        tp = info.get('targetMeanPrice')
        if cp and tp and tp > cp * 1.10: score += 1
        
        # 10. Rec Mean <= 2.5
        rec = info.get('recommendationMean')
        if rec and rec <= 2.5: score += 1
        
        # 11. YoY R&D Expense Increase
        if 'Research And Development' in financials.index and prev:
            if financials.loc['Research And Development', curr] > financials.loc['Research And Development', prev]: score += 1
        
    except Exception: pass
    return (score / 11.0) * 100.0

def generate_fundamental_views(tickers):
    """
    Computes 8 fundamental factors and returns a normalized score (0 to 1) per ticker.
    """
    views = pd.Series(0.0, index=tickers)
    
    # Internal module weights based on AGENTS.md relative proportions
    FACTOR_WEIGHTS = {
        "Custom_Balance": 0.1667,
        "Custom_Growth": 0.1667,
        "GrossIncome_Assets": 0.05,
        "RnD_MarketCap": 0.05,
        "RnD_Assets": 0.05,
        "Innovative_ROE": 0.05,
        "Price_Target": 0.05,
        "Dividend_Yield": 0.05
    }
    
    total_module_weight = sum(FACTOR_WEIGHTS.values())
    
    for ticker in tickers:
        data = get_fundamental_data(ticker)
        if data is None:
            views[ticker] = 0.0
            continue
            
        info = data['info']
        financials = data['financials']
        balancesheet = data['balancesheet']
        
        scores = {}
        try:
            scores["Custom_Balance"] = score_custom_balance(data)
            scores["Custom_Growth"] = score_custom_growth(data)
            
            if not financials.empty and 'Gross Profit' in financials.index and not balancesheet.empty and 'Total Assets' in balancesheet.index:
                gi_a = financials.loc['Gross Profit', financials.columns[0]] / balancesheet.loc['Total Assets', balancesheet.columns[0]]
                scores["GrossIncome_Assets"] = min(100.0, max(0.0, gi_a * 100.0))
            else: scores["GrossIncome_Assets"] = 0.0
                
            mc = info.get('marketCap', 0)
            rnd = financials.loc['Research And Development', financials.columns[0]] if 'Research And Development' in financials.index else 0
            
            if mc and mc > 0: scores["RnD_MarketCap"] = min(100.0, (rnd / mc) * 1000.0)
            else: scores["RnD_MarketCap"] = 0.0
                
            if rnd > 0 and not balancesheet.empty and 'Total Assets' in balancesheet.index:
                rnd_a = rnd / balancesheet.loc['Total Assets', balancesheet.columns[0]]
                scores["RnD_Assets"] = min(100.0, rnd_a * 500.0)
            else: scores["RnD_Assets"] = 0.0
                
            if not financials.empty and 'Net Income' in financials.index and not balancesheet.empty and 'Stockholders Equity' in balancesheet.index:
                ni = financials.loc['Net Income', financials.columns[0]]
                equity = balancesheet.loc['Stockholders Equity', balancesheet.columns[0]]
                if equity > 0:
                    iroe = (ni + rnd) / equity
                    scores["Innovative_ROE"] = min(100.0, max(0.0, iroe * 100.0))
                else: scores["Innovative_ROE"] = 0.0
            else:
                roe = info.get('returnOnEquity', 0)
                scores["Innovative_ROE"] = min(100.0, max(0.0, (roe if roe else 0) * 100.0))
                
            cp = info.get('currentPrice')
            tp = info.get('targetMeanPrice')
            if cp and tp and tp > 0:
                # Eval 1: Direct comparison of cp/tp in same currency from yf info
                ratio = cp / tp
                scores["Price_Target"] = max(0.0, min(100.0, (1.5 - ratio) * 100.0))
            else: scores["Price_Target"] = 50.0
                
            dy = info.get('dividendYield', 0)
            scores["Dividend_Yield"] = min(100.0, (dy if dy else 0) * 1000.0)
            
        except Exception:
            views[ticker] = 0.0
            continue
            
        ticker_score = sum(scores[f] * FACTOR_WEIGHTS[f] for f in FACTOR_WEIGHTS) / total_module_weight
        views[ticker] = ticker_score
        
    max_val = views.abs().max()
    if max_val > 0: views = views / max_val
    return views