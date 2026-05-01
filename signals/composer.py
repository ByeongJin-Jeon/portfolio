import pandas as pd
import numpy as np
import yfinance as yf
from signals.trend import generate_trend_views
from signals.fundamental import generate_fundamental_views
from signals.options_skew import generate_options_skew_views
from signals.macro import get_macro_expected_returns, get_macro_signals, apply_macro_filters
from portfolio.factor_loading import fetch_ff_factors, extract_idiosyncratic_alpha
from config import Q_WEIGHTS, VIX_KILLSWITCH, FX_KILLSWITCH_LIMIT, DEFENSIVE_ETFS

def compose_bl_inputs(prices, volumes=None):
    """
    Orchestrates Tactical Signals with the new 13-factor model.
    """    
    print("📡 Orchestrating Tactical Signals with 13-Factor Model...")

    tickers = prices.columns.tolist()
    returns = prices.pct_change(fill_method=None).dropna()

    current_date = prices.index[-1].tz_localize(None)
    today_date = pd.Timestamp.now().tz_localize(None)
    
    is_time_machine_mode = (today_date - current_date).days > 15

    # 1. Technical Trends (Updated to include volumes)
    print(f"1️⃣  Calculating Trend Factors (Minervini QM, etc.)...")
    if volumes is None:
        # Fallback if volumes not provided
        volumes = pd.DataFrame(1.0, index=prices.index, columns=prices.columns)
    
    Q_trend = generate_trend_views(prices, volumes)

    # 2. Macro & Kill-Switch
    if is_time_machine_mode:
        Q_macro = pd.Series(0.0, index=tickers)
        Q_skew = pd.Series(0.0, index=tickers)
        macro_signals = {
            "kill_switch": False, 
            "vix_level": 20.0, 
            "vix_scalar": 1.0,
            "tilt_to_quality": False
        }
        base_kill_switch = False
        vix_trigger = False
        fx_trigger = False
        fx_volatility = 0.0
    else:
        Q_macro = get_macro_expected_returns(tickers)
        Q_skew = generate_options_skew_views(tickers)
        macro_signals = get_macro_signals()
        
        vix_level = macro_signals.get("vix_level", 20.0)
        if isinstance(vix_level, (pd.Series, pd.DataFrame)): vix_level = vix_level.iloc[-1]
        vix_trigger = vix_level > VIX_KILLSWITCH
        
        base_kill_switch = macro_signals.get("kill_switch", False)
        
        try:
            fx_data = yf.download("USDKRW=X", period="10d", interval="1d", progress=False)['Close']
            if isinstance(fx_data, pd.DataFrame): recent_fx = fx_data.iloc[:, 0].tail(5)
            else: recent_fx = fx_data.tail(5)
            fx_volatility = (recent_fx.max() / recent_fx.min()) - 1
        except Exception: fx_volatility = 0.0
        fx_trigger = fx_volatility > FX_KILLSWITCH_LIMIT

    # 3. Fundamental & Smart money
    print(f"2️⃣  Calculating Fundamental Factors (Balance, Growth, ROE, etc.)...")
    Q_fundamental = generate_fundamental_views(tickers)

    # 4. Idiosyncratic alpha
    print(f"3️⃣  Extracting Idiosyncratic Alpha...")
    try:
        ff_factors = fetch_ff_factors()
        Q_alpha = extract_idiosyncratic_alpha(returns, ff_factors)
    except Exception:
        Q_alpha = pd.Series(0.0, index=tickers)

    # Combine signals
    # Since AGENTS.md provides specific weights for 13 factors which reside in Q_trend and Q_fundamental,
    # we'll assume Q_trend and Q_fundamental already contain their internal weighted sums.
    # The AGENTS.md total weight for Trend is ~0.3667 and Fundamental is ~0.6334.
    
    # W_trend = 0.3667
    # W_fundamental = 0.6334
    
    # final_raw_q = (Q_trend * W_trend).add(Q_fundamental * W_fundamental, fill_value=0)
    
    # Add optional alpha and skew (using config weights as secondary adjustment or keeping them separate)
    # To strictly follow AGENTS.md, we might focus on the 13 factors.
    # But for resilience, we blend with macro/skew/alpha.
    ann_volatility = returns.std() * np.sqrt(252)

    trend_multiplier = (Q_trend - 0.5) * 2.0
    fundamental_multiplier = (Q_fundamental - 0.5) * 2.0

    Q_trend = trend_multiplier * ann_volatility * 0.5
    Q_fundamental = fundamental_multiplier * ann_volatility * 0.5
    
    final_raw_q = (Q_trend * Q_WEIGHTS['trend']) \
                .add(Q_fundamental * Q_WEIGHTS['fundamental'], fill_value=0) \
                .add(Q_skew * Q_WEIGHTS['skew'], fill_value=0) \
                .add(Q_alpha * Q_WEIGHTS['alpha'], fill_value=0)
    
    final_raw_q = final_raw_q.fillna(0.0)

    q_df = pd.DataFrame({"Q_trend": Q_trend,
                         "Q_fundamental": Q_fundamental,
                         "Q_skew": Q_skew,
                         "Q_alpha": Q_alpha,
                         "final_raw_q": final_raw_q})
    q_df.to_csv('outputs/Q_matrix.csv')

    # Kill-Switch & Filters
    combined_kill_switch = bool(base_kill_switch or vix_trigger or fx_trigger)
    macro_signals["global_kill_switch"] = combined_kill_switch
    macro_signals["kr_kill_switch"] = fx_trigger
    
    final_q_views = apply_macro_filters(final_raw_q, macro_signals)

    # Eval 2: Dynamic Penalty & Defensive ETF boost
    print("\n🛡️ Applying Tactical Penalties & Defensive Boosts...")
    for ticker in final_q_views.index:
        clean_t = str(ticker).split('.')[0]
        if clean_t in DEFENSIVE_ETFS:
            if not combined_kill_switch:
                final_q_views[ticker] = -2.0 # Risk-On: penalize defensive
            else:
                final_q_views[ticker] = 2.0  # Risk-Off: boost defensive
        else:
            if combined_kill_switch:
                # Force stocks down during kill-switch
                final_q_views[ticker] = -1.0
                
    vix_scalar = macro_signals.get("vix_scalar", 1.0)
    initial_omega = pd.Series(1.0 * vix_scalar, index=final_q_views.index)
    
    return final_q_views, initial_omega, combined_kill_switch