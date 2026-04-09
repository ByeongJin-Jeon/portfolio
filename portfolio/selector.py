# -*- coding: utf-8 -*-
import pandas as pd
from config import MAX_ASSETS, CSV_ENCODING

def select_final_portfolio(bl_weights, liquidity_caps, kr_floor=0.06):
    """
    Applies liquidity caps and selects the Top 10 assets.
    Ensures data types are aligned for scalar comparison.
    하이브리드 전략 적용: 한국 5개(최소 30%) + 미국 5개(나머지 70%) 선정
    """
    # 1. 형식 변환
    weights = bl_weights.iloc[:, 0] if isinstance(bl_weights, pd.DataFrame) else bl_weights.copy()

    # 2. 유동성 제약 적용
    for asset in weights.index:
        if asset in liquidity_caps.index:
            weights.loc[asset] = min(float(weights.loc[asset]), float(liquidity_caps.loc[asset]))

    # 3. 국가별 상위 종목 분리 (한국: 숫자 티커 / 미국: 문자 티커)
    kr_pool = weights[weights.index.map(lambda x: str(x).isdigit())]
    us_pool = weights[~weights.index.map(lambda x: str(x).isdigit())]

    # 각 국가별 상위 5개씩 선정
    top_kr = kr_pool.nlargest(5)
    top_us = us_pool.nlargest(5)

    # 4. [핵심] 최소 비중(Floor) 보정 로직
    # 한국 종목 5개에 각각 6%씩 할당 (합계 30%)
    final_kr = pd.Series(kr_floor, index=top_kr.index)
    
    # 남은 비중 70%를 미국 종목 5개에 원래 HRP/BL 비중 비율대로 배분
    remaining_total = 1.0 - final_kr.sum()
    final_us = (top_us / top_us.sum()) * remaining_total

    # 5. 최종 합체
    final_portfolio = pd.concat([final_kr, final_us]).sort_values(ascending=False)
    
    return final_portfolio  

def export_portfolio(weights, path):
    """Outputs the final allocation to terminal and CSV."""
    print("\n--- GEOPOLITICALLY RESILIENT PORTFOLIO (TOP 10) ---")
    print(weights)
    weights.to_csv(path, encoding=CSV_ENCODING)