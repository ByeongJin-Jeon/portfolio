# -*- coding: utf-8 -*-
import pandas as pd
import yfinance as yf

def is_kr_ticker(ticker):
    return str(ticker)[0].isdigit()

def generate_options_skew_views(tickers):
    """
    Dual Smart Money Engine:
    1. Macro Tail Risk (CBOE ^SKEW): Is the entire market bracing for a Black Swan?
    2. Micro Asset Skew (Put-Call IV Spread): Are whales betting against specific assets (EWY for KR)?
    """
    Q_skew = pd.Series(0.0, index=tickers)
    
    # ---------------------------------------------------------
    # PART 1: Macro SKEW (^SKEW) - The "Casino Fire" Penalty
    # ---------------------------------------------------------
    macro_penalty = 0.0
    try:
        skew_data = yf.download('^SKEW', period='1mo', progress=False)
        if not skew_data.empty:
            if isinstance(skew_data.columns, pd.MultiIndex):
                latest_skew = float(skew_data['Close']['^SKEW'].iloc[-1])
            else:
                latest_skew = float(skew_data['Close'].iloc[-1])
                
            print(f"   -> [MACRO] CBOE SKEW Index: {latest_skew:.2f}")
            if latest_skew >= 140.0:
                print("   -> [ALERT] Macro SKEW >= 140! Applying blanket -5% penalty.")
                macro_penalty = -0.05
            elif latest_skew >= 135.0:
                macro_penalty = -0.02
    except Exception as e:
        print(f"   -> [WARNING] Failed to fetch ^SKEW: {e}")

    # ---------------------------------------------------------
    # PART 2: Micro Skew (EWY Proxy) - The "Targeted Hit"
    # ---------------------------------------------------------
    ewy_skew_return = 0.0
    try:
        ewy = yf.Ticker('EWY')
        ewy_exp = ewy.options
        if ewy_exp:
            opt = ewy.option_chain(ewy_exp[0])
            current_price = ewy.history(period="1d")['Close'].iloc[-1]
            
            lower_bound = current_price * 0.80
            upper_bound = current_price * 1.20
            
            otm_calls = opt.calls[(opt.calls['strike'] > current_price) & (opt.calls['strike'] <= upper_bound)]
            otm_puts = opt.puts[(opt.puts['strike'] < current_price) & (opt.puts['strike'] >= lower_bound)]
            
            valid_calls = otm_calls[(otm_calls['volume'].fillna(0) > 0) & (otm_calls['openInterest'].fillna(0) > 0)]
            valid_puts = otm_puts[(otm_puts['volume'].fillna(0) > 0) & (otm_puts['openInterest'].fillna(0) > 0)]
            
            if not valid_calls.empty and not valid_puts.empty:
                call_target_strike = current_price * 1.05
                put_target_strike = current_price * 0.95
                
                closest_call = valid_calls.iloc[(valid_calls['strike'] - call_target_strike).abs().argsort()[:1]]
                closest_put = valid_puts.iloc[(valid_puts['strike'] - put_target_strike).abs().argsort()[:1]]
                
                if not closest_call.empty and not closest_put.empty:
                    call_iv = closest_call['impliedVolatility'].values[0]
                    put_iv = closest_put['impliedVolatility'].values[0]
                    
                    iv_skew = put_iv - call_iv
                    
                    print(f"   -> [MICRO] EWY 5% OTM Skew: {iv_skew:.4f} (Put {put_iv:.2f} vs Call {call_iv:.2f})")
                    
                    if iv_skew > 0.08:
                        ewy_skew_return = -0.05 
                        print("   -> [BEARISH] Smart money is buying EWY Puts!")
                    elif iv_skew < -0.02:
                        ewy_skew_return = 0.05  
                        print("   -> [BULLISH] Smart money is buying EWY Calls!")
                    else:
                        print("   -> [NEUTRAL] Options market is balanced.")
            else:
                print("   -> [INFO] EWY lacks valid volume for Skew calculation. Assuming Neutral.")

    except Exception as e:
        print(f"   -> [WARNING] Failed to fetch EWY options: {e}")

    # ---------------------------------------------------------
    # PART 3: Assemble the Final Q_skew
    # ---------------------------------------------------------
    for ticker in tickers:
        asset_micro_return = 0.0
        
        # Apply EWY proxy for Korean assets
        if is_kr_ticker(ticker):
            asset_micro_return = ewy_skew_return
        else:
            # For US assets, calculate individual IV Skew (Your original logic)
            try:
                stock = yf.Ticker(ticker)
                exp = stock.options
                if exp:
                    opt = stock.option_chain(exp[0])
                    curr_p = stock.history(period="1d")['Close'].iloc[-1]
                    
                    lower_bound = current_price * 0.80
                    upper_bound = current_price * 1.20
                    
                    otm_calls = opt.calls[(opt.calls['strike'] > curr_p) & (opt.calls['strike'] <= upper_bound)]
                    otm_puts = opt.puts[(opt.puts['strike'] < curr_p) & (opt.puts['strike'] >= lower_bound)]
                    
                    valid_calls = otm_calls[(otm_calls['volume'].fillna(0) > 0) & (otm_calls['openInterest'].fillna(0) > 0)]
                    valid_puts = otm_puts[(otm_puts['volume'].fillna(0) > 0) & (otm_puts['openInterest'].fillna(0) > 0)]
                    
                    if not valid_calls.empty and not valid_puts.empty:
                        call_target_strike = current_price * 1.05
                        put_target_strike = current_price * 0.95
                        
                        closest_call = valid_calls.iloc[(valid_calls['strike'] - call_target_strike).abs().argsort()[:1]]
                        closest_put = valid_puts.iloc[(valid_puts['strike'] - put_target_strike).abs().argsort()[:1]]
                        
                        if not closest_call.empty and not closest_put.empty:
                            call_iv = closest_call['impliedVolatility'].values[0]
                            put_iv = closest_put['impliedVolatility'].values[0]
                            
                            iv_skew = put_iv - call_iv

                            if iv_skew > 0.08:
                                asset_micro_return = -0.05 
                            elif iv_skew < -0.02:
                                asset_micro_return = 0.05  
                            else:
                                continue
            except:
                pass # Skip silently if US asset has no options
                
        # Final Score = Macro Penalty + Asset-Specific Smart Money Flow
        Q_skew[ticker] = macro_penalty + asset_micro_return

    return Q_skew