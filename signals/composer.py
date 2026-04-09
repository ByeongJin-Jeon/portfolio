import pandas as pd
import numpy as np
import yfinance as yf
from signals.trend import generate_trend_views
from signals.macro import get_macro_signals, apply_macro_filters

def compose_bl_inputs(prices):
    """
    [Stage 3] 통합 지휘소: Trend + Macro + FX Volatility 킬스위치 가동
    """
    print("📡 Orchestrating Tactical Signals with FX Watchdog...")

    # 1. Macro 모듈에서 기초 신호 획득 (VIX, TIPS 등)
    macro_signals = get_macro_signals()

    def to_latest_bool(val):
        if isinstance(val, (pd.Series, pd.DataFrame)):
            return bool(val.iloc[-1])
        return bool(val)
    
    base_kill_switch = to_latest_bool(macro_signals.get("kill_switch", False))

    vix_level = macro_signals.get("vix_level", 20.0)
    if isinstance(vix_level, (pd.Series, pd.DataFrame)):
        vix_level = vix_level.iloc[-1]
    
    # 2. [추가] 실시간 환율 킬스위치 로직
    print("💱 Checking FX Volatility (USD/KRW)...")
    fx_data = yf.download("USDKRW=X", period="10d", interval="1d", progress=False)['Close']
    
    # 최근 5일간 최저점 대비 최고점 변동폭 계산
    recent_fx = fx_data.tail(5)
    fx_volatility = (recent_fx.max() / recent_fx.min()) - 1
    fx_volatility = fx_volatility['USDKRW=X']
    
    # 킬스위치 조건 통합: VIX 25 초과 OR 환율 5일 내 3% 급변
    vix_trigger = vix_level > 25
    fx_trigger_raw = fx_volatility > 0.03 # 3% 변동성
    fx_trigger = bool(fx_trigger_raw.any())
    
    # 최종 킬스위치 결정
    combined_kill_switch = bool(base_kill_switch or vix_trigger or fx_trigger)
    
    # 3. Trend 모듈에서 기초 뷰(Q) 획득
    trend_views = generate_trend_views(prices)
    
    # 4. 매크로 필터 적용 (킬스위치 작동 시 주식 비중 Zero화)
    macro_signals["kill_switch"] = combined_kill_switch
    final_q_views = apply_macro_filters(trend_views, macro_signals)
    
    # 5. 블랙-리터먼 확신도(Omega) 조절
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