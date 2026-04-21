# -*- coding: utf-8 -*-
import pandas as pd
import yfinance as yf

def is_kr_ticker(ticker):
    return str(ticker)[0].isdigit()

def generate_options_skew_views(tickers):
    """
    Put-Call Volatility Skew
    """
    skew_views = pd.Series(0.0, index=tickers)

    ewy_skew_value = 0.0
    try:
        ewy = yf.Ticker('EWY')
        ewy_exp = ewy.options
        if ewy_exp:
            opt = ewy.option_chain(ewy_exp[0])
            current_price = ewy.history(period="1d")['Close'].iloc[-1]
            
            otm_calls = opt.calls[opt.calls['strike'] > current_price]
            otm_puts = opt.puts[opt.puts['strike'] < current_price]
            
            call_iv = otm_calls['impliedVolatility'].mean()
            put_iv = otm_puts['impliedVolatility'].mean()
            
            ewy_skew = put_iv - call_iv
            if ewy_skew > 0.10:
                ewy_skew_value = -1.0 # 하락 베팅 우세
            elif ewy_skew < -0.05:
                ewy_skew_value = 1.0  # 상승 베팅 우세
    except Exception as e:
        print(f"Impossible to get EWY option skew: {e}")
    
    for ticker in tickers:
        try:
            if is_kr_ticker(ticker):
                skew_views[ticker] = ewy_skew_value
                continue

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
                
        except Exception as e:
            skew_views[ticker] = 0.0
            
    return skew_views