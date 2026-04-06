# -*- coding: utf-8 -*-
"""
signals/composer.py
===================
The Central Command: Orchestrates Trend views and Macro filters into BL inputs.
"""

import pandas as pd
import numpy as np
from signals.trend import generate_trend_views
from signals.macro import get_macro_signals, apply_macro_filters

def compose_bl_inputs(prices):
    """
    [Stage 3] 통합 지휘소: trend.py와 macro.py를 연결하여 최종 뷰(Q)와 확신(Omega) 생성
    """
    print("📡 Orchestrating Tactical Signals...")

    # 1. Trend 모듈에서 기초 뷰(Q) 획득 (MA Alignment & Envelope)
    # trend.py의 generate_trend_views는 이미 5/22/60/182 로직이 반영됨
    trend_views = generate_trend_views(prices)
    
    # 2. Macro 모듈에서 위기 신호 및 필터 획득
    # VIX, 킬스위치, TIPS 스파이크 신호를 싹 다 가져옴
    macro_signals = get_macro_signals()
    
    # 3. 매크로 필터 적용 (킬스위치 작동 시 주식 비중 Zero화 및 안전자산 로테이션)
    # macro.py의 apply_macro_filters가 이 작업을 수행함
    final_q_views = apply_macro_filters(trend_views, macro_signals)
    
    # 4. 블랙-리터먼 확신도(Omega) 조절
    # VIX가 높을수록 불확실성이 크다고 보고 Omega 값을 키워줌 (vix_scalar 활용)
    # Omega가 커지면 BL 모델이 우리 뷰(Q)를 덜 믿고 HRP Prior에 더 집중하게 됨
    vix_scalar = macro_signals.get("vix_scalar", 1.0)
    
    # 기초 Omega (1.0) 에 VIX 스칼라를 곱해서 불확실성 반영
    # 나중에 factor_loading.py에서 산출한 고유 리스크와 결합될 예정
    initial_omega = pd.Series(1.0 * vix_scalar, index=final_q_views.index)
    
    kill_switch_active = macro_signals["kill_switch"]
    
    if kill_switch_active:
        print(f"🚨 [ALERT] Macro Kill-Switch Active! (VIX: {macro_signals['vix_level']:.2f})")
        if macro_signals["tilt_to_quality"]:
            print("💎 [TILT] Real Rate Spike detected. Shifting to Quality/SafeHaven.")

    return final_q_views, initial_omega, kill_switch_active