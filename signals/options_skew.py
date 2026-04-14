# -*- coding: utf-8 -*-
import pandas as pd
import yfinance as yf

def generate_options_skew_views(tickers):
    """
    Put-Call Volatility Skew
    """
    skew_views = pd.Series(0.0, index=tickers)
    
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            expirations = stock.options
            
            if not expirations:
                continue
                
            # Option chain with the nearest expiration date
            opt = stock.option_chain(expirations[0])
            calls = opt.calls
            puts = opt.puts
            
            # Calculation of the average implied volatility (IV) of OTM (out-of-the-money) options
            current_price = stock.history(period="1d")['Close'].iloc[-1]
            
            otm_calls = calls[calls['strike'] > current_price]
            otm_puts = puts[puts['strike'] < current_price]
            
            call_iv = otm_calls['impliedVolatility'].mean()
            put_iv = otm_puts['impliedVolatility'].mean()
            
            # Skew = Put IV - Call IV
            iv_skew = put_iv - call_iv
            
            if iv_skew > 0.10:
                skew_views[ticker] = -1.0
            elif iv_skew < -0.05:
                skew_views[ticker] = 1.0
                
        except Exception:
            skew_views[ticker] = 0.0
            
    return skew_views