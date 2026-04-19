import pandas as pd
import numpy as np
import yfinance as yf
from signals.trend import generate_trend_views
from signals.fundamental import generate_fundamental_views
from signals.options_skew import generate_options_skew_views
from signals.macro import get_macro_signals, apply_macro_filters
from portfolio.factor_loading import fetch_ff_factors, extract_idiosyncratic_alpha
from config import Q_WEIGHTS, VIX_KILLSWITCH, FX_KILLSWITCH_LIMIT

def compose_bl_inputs(prices):
    print("📡 Orchestrating Tactical Signals with FX Watchdog...")

    tickers = prices.columns.tolist()
    returns = prices.pct_change(fill_method=None).dropna()

    print(f"1️⃣  Technical Trends ({Q_WEIGHTS['trend'] * 100}% weight)")
    Q_trend = generate_trend_views(prices)
    if isinstance(Q_trend, pd.DataFrame):
        Q_trend = Q_trend.iloc[-1]

    print(f"2️⃣  Fundamental & Smart money ({Q_WEIGHTS['fundamental'] * 100}% weight)")
    Q_fundamental = generate_fundamental_views(tickers)

    print(f"3️⃣  Idiosyncratic alpha ({Q_WEIGHTS['alpha'] * 100}% weight)")
    try:
        ff_factors = fetch_ff_factors()
        Q_alpha = extract_idiosyncratic_alpha(returns, ff_factors)
    except Exception as e:
        print(f"⚠️ Fail to collect FF5 factor: {e}")
        Q_alpha = pd.Series(0.0, index=tickers)

    print(f"4️⃣  Put-call volatility skew ({Q_WEIGHTS['skew'] * 100}% weight)")
    Q_skew = generate_options_skew_views(tickers)

    final_raw_q = (Q_trend * Q_WEIGHTS['trend']).add(Q_fundamental * Q_WEIGHTS['fundamental'], fill_value=0) \
                                 .add(Q_alpha * Q_WEIGHTS['alpha'], fill_value=0) \
                                 .add(Q_skew * Q_WEIGHTS['skew'], fill_value=0)
    
    final_raw_q = final_raw_q.fillna(0.0)

    macro_signals = get_macro_signals()

    def to_latest_bool(val):
        if isinstance(val, (pd.Series, pd.DataFrame)):
            return bool(val.iloc[-1])
        return bool(val)
    
    base_kill_switch = to_latest_bool(macro_signals.get("kill_switch", False))

    vix_level = macro_signals.get("vix_level", 20.0)
    if isinstance(vix_level, (pd.Series, pd.DataFrame)):
        vix_level = vix_level.iloc[-1]
    
    print("💱 Checking FX Volatility (USD/KRW)...")
    fx_data = yf.download("USDKRW=X", period="10d", interval="1d", progress=False)['Close']

    recent_fx = fx_data.tail(5)
    fx_volatility = (recent_fx.max() / recent_fx.min()) - 1
    fx_volatility = fx_volatility['USDKRW=X']

    vix_trigger = vix_level > VIX_KILLSWITCH
    fx_trigger_raw = fx_volatility > FX_KILLSWITCH_LIMIT
    fx_trigger = bool(fx_trigger_raw.any())

    macro_signals["global_kill_switch"] = bool(base_kill_switch or vix_trigger)
    macro_signals["kr_kill_switch"] = fx_trigger
    
    combined_kill_switch = bool(base_kill_switch or vix_trigger or fx_trigger)
    
    final_q_views = apply_macro_filters(final_raw_q, macro_signals)
    
    vix_scalar = macro_signals.get("vix_scalar", 1.0)
    initial_omega = pd.Series(1.0 * vix_scalar, index=final_q_views.index)
    
    if combined_kill_switch:
        print(f"🚨🚨 [DANGER] Kill-Switch ACTIVATED!")
        if vix_trigger: print(f"   - Cause: High VIX ({vix_level:.2f})")
        if fx_trigger: print(f"   - Cause: FX Volatility ({fx_volatility*100:.2f}%)")
        print("   >>> Strategy: Moving to Cash/Safe-Haven mode.")
    else:
        print(f"🟢 [SAFE] Markets Stable (VIX: {vix_level:.2f}, FX Vol: {fx_volatility*100:.2f}%)")

    return final_q_views, initial_omega, combined_kill_switch