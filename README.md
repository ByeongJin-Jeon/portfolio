# Geopolitically Resilient Multi-Asset Allocation Engine

A **Resilience-First Quantitative Allocation Engine** engineered to maintain structural integrity during systemic market failures — including the 2008 Global Financial Crisis, the 2020 COVID Liquidity Crisis, and projected 2026 geopolitical instabilities.

The system integrates **Hierarchical Risk Parity (HRP)** as a Bayesian prior, **Black-Litterman (BL)** optimization with a proprietary **4-Pillar Alpha Engine**, and **Conditional Drawdown at Risk (CDaR)** constraints. The engine now features a **Walk-Forward Time Machine** that executes monthly rolling rebalancing across historical crisis windows without look-ahead bias.

---

## System Architecture

The engine executes a recursive **Walk-Forward Pipeline**. In backtest mode, it iterates through time, presenting the optimizer only with data available up to each rebalance date.

```
UniverseManager → DataLoader → [ WALK-FORWARD RECURSION ]
                                      ↓ (Monthly)
                         my_quant_strategy(past_prices)
                                      ↓
                SignalComposer → FactorLoading → HRP Prior
                       ↓               ↓              ↓
                Time-Machine    Idio. Variance   Bayesian Prior
                 (Macro/Skew)    (Omega matrix)
                                      ↓
                        Black-Litterman Optimization
                         (CDaR ≤ 15%, Maximize UPI)
                                      ↓
                         Liquidity-Capped Selector
                                      ↓
                        [ vectorbt Portfolio Engine ]
                                      ↓
                      3-Scenario Resilience Scorecard
                   (GFC 2008 / COVID 2020 / MIDEAST 2026)
```

---

## Module Reference

| Module | File(s) | Role |
| :--- | :--- | :--- |
| **Universe Construction** | `data/universe.py` | Scrapes S&P 500, NASDAQ-100, Dow Jones from Wikipedia; KOSPI 200 via `FinanceDataReader`. Merges with Core & Defensive ETF lists from `config.py`. |
| **Data Ingestion** | `data/loader.py` | Fetches OHLCV in 50-ticker chunks via `yfinance`. KRX tickers are suffixed `.KS` for download then mapped back to numeric codes. Prices saved as `utf-8-sig` CSV to preserve Hangul. |
| **Signal Composition** | `signals/composer.py` | Orchestrates the **13-Factor Alpha Engine**. Includes **Time-Machine Mode** which bypasses live API calls for historical dates to prevent data leakage and API failures during backtests. |
| **Trend Engine** | `signals/trend.py` | Uses yesterday's data (`shift(1)`) to compute **Minervini QM Scoring**, 6M Momentum, Volume/Price CV, Upside Potential, and the **Cash Flow Per Share (CPS) Trend Line**. |
| **Fundamental Engine** | `signals/fundamental.py` | Comprehensive scoring across 8 factors: **Custom Balance**, **Custom Growth**, Gross Income/Assets, R&D/MarketCap, R&D/Assets, **Innovative ROE**, Price Target, and Dividend Yield. |
| **Idiosyncratic Alpha** | `portfolio/factor_loading.py` | OLS regression against Fama-French 5-Factor daily data. Assets with positive residuals over 20 days receive alpha views; residual variance populates the **Omega matrix**. |
| **Black-Litterman Optimizer** | `optimization/black_litterman.py` | Combines HRP prior, 13-factor Q-views, and Omega. Optimizes for **max Ulcer Performance Index (UPI)** subject to CDaR ≤ 15%. |
| **Backtest Engine** | `backtest/engine.py` | **Walk-Forward Controller**. Executes monthly rebalancing by calling the strategy pipeline for every month in the scenario window. Strictly enforces No-Look-Ahead bias. |
| **Evaluation Metrics** | `evaluation/metrics.py` | Computes MDD, Ulcer Index (`√mean(drawdown²)`), Serenity Ratio, and Calmar Ratio from the `vectorbt` portfolio object. |

---

## The Walk-Forward "Time Machine"

To ensure the engine's resilience is empirically valid, the backtest engine (`backtest/engine.py`) operates under a strict **Walk-Forward Protocol**:

1. **Monthly Rebalancing**: The engine steps through time month-by-month.
2. **Point-in-Time Data**: At each step, the entire optimization pipeline (`my_quant_strategy`) is called using ONLY `prices.loc[:current_date]`.
3. **Time-Machine Mode**: In `signals/composer.py`, the system detects if `current_date` is in the past. If so, it bypasses live-only signals (like real-time FX volatility or options skew from live chains) and uses neutral priors or cached historical proxies to avoid look-ahead bias.
4. **Liquidity Realism**: Weight caps are recalculated at every step based on the rolling 20-day volume *at that specific point in time*.

---

## The 13-Factor Alpha Engine

Q-views are composed as a weighted sum of four independent signal pillars, which themselves aggregate **13 independent sub-factors**. Weights are configurable in `config.Q_WEIGHTS`.

| Pillar | Default Weight | Key Sub-Factors |
| :--- | :---: | :--- |
| **Fundamental** | 40% | Custom Balance, Custom Growth, Innovative ROE, R&D/Assets, Gross Income/Assets, Price Target, Dividend Yield |
| **Technical Trend** | 20% | Minervini QM Score, 6M Return, Volume/Price CV, Upside Potential, CPS Trend Line |
| **Idiosyncratic Alpha** | 20% | Fama-French 5-Factor OLS residuals (rolling 20-day mean) |
| **Options Skew** | 20% | OTM Put IV − Call IV (Bearish/Bullish view based on tail-risk pricing) |

---

## Macro Risk Layers

Three independent kill-switches operate in the signal composition stage with dynamic tactical adjustments:

**1. Global VIX Kill-Switch** (`VIX_KILLSWITCH = 30`)
- If `^VIX ≥ 30`, the system enters **Safe-Haven Mode**.
- **Tactical Adjustments**:
    - Defensive ETF Q-views are set to `+2.0` (Hard Buy).
    - All Equity Q-views are set to `-1.0` (Hard Sell).
- Confidence scalar: `1 + max(0, (VIX − 20) / 20)` inflates the Omega uncertainty matrix above VIX 20, widening asset view intervals.

**2. KR FX Kill-Switch** (`FX_KILLSWITCH_LIMIT = 5%`)
- If the 5-day USD/KRW range exceeds 5%, all KRX-side Q-views are zeroed.
- Capital is implicitly redirected to USD-denominated assets and SGOV/SOFR proxies.

**3. Risk-On vs. Risk-Off Tactical Tilt**
- **Risk-On (Kill-Switch Off)**: Defensive ETFs are penalized with a `-2.0` view to prevent drag during bull markets.
- **Risk-Off (Kill-Switch On)**: Stocks are penalized (`-1.0`) while Defensive ETFs are boosted (`+2.0`).
- **TIPS Real-Rate Spike**: If `TIP` ETF falls > 1% daily, a Quality Tilt is applied (Growth x0.5, Value/Defensive x1.5).


---

## Optimization Stack

```
HRP Prior (riskfolio HCPortfolio, Ward linkage, Pearson distance)
    ↓
Black-Litterman posterior (δ=2.5, τ=0.05, Omega=idio_var×τ)
    ↓
[Stage 1] Maximize Sharpe (rm=CVaR) subject to CDaR ≤ 15%
    ↓ (if solver fails)
[Stage 2] Minimize CDaR Risk (no constraint, ECOS solver)
    ↓ (if solver fails again)
[Stage 3] Return raw HRP weights
```

Portfolio constraints applied post-optimization:
- Per-asset weight floor: 1% (`MIN_WEIGHT`)
- Per-asset weight ceiling: 50% (`MAX_WEIGHT_SINGLE`), further capped by liquidity
- Final selection: top 10 assets by weight (`MAX_ASSETS`)

---

## Stress-Testing Scenarios

| Scenario | Window | Archetype |
| :--- | :--- | :--- |
| `GFC_2008` | 2007-07-01 → 2009-06-30 | Credit contraction, banking sector collapse |
| `COVID_2020` | 2019-10-01 → 2021-03-31 | Exogenous liquidity shock, VIX spike to 80+ |
| `MIDEAST_2026` | 2025-10-01 → present | Energy price surge, stagflationary supply shock |

Assets not listed during a given window are automatically excluded and weights are renormalized.

**Resilience Metrics Reported per Scenario:**

| Metric | Formula |
| :--- | :--- |
| Annualized Return | `vectorbt` built-in |
| Max Drawdown (MDD) | Peak-to-trough decline |
| Ulcer Index (UI) | `√ mean(drawdown²)` |
| Serenity Ratio | `Ann. Return / (UI × \|MDD\|)` |
| Calmar Ratio | `Ann. Return / \|MDD\|` |

---

## Asset Universe

The engine scans **800+ global candidates** at startup:

- **US Equities**: Full S&P 500 + NASDAQ-100 + Dow Jones (scraped live from Wikipedia)
- **KR Equities**: Top 200 KOSPI names via `FinanceDataReader`
- **Core ETFs**: SPY, DBC, VNQ, XLK, XLE, XLV, KODEX 200 (069500), TIGER 200 IT (139260)
- **Defensive ETFs**: TLT, IEF, SHV, SGOV, GLD, KODEX 국고채3년 (114260), KOEF 국고채10년 (148070), ACE SOFR (229200)

Candidates are filtered down to approximately 50 names using a 60-day risk-adjusted momentum score before optimization.

---

## Setup & Execution

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Key libraries: `yfinance`, `FinanceDataReader`, `riskfolio-lib`, `vectorbt`, `statsmodels`, `pandas_datareader`, `requests`

### 2. Run the Pipeline

```bash
python main.py
```

The pipeline will:
1. Scan the full global universe (~800 tickers)
2. Fetch and cache price/volume data from `PRICE_START` (2006-01-01) to today
3. Convert all prices to KRW
4. Filter to ~50 momentum-quality candidates
5. Compute 4-pillar Q-views and apply macro filters
6. Run HRP → Black-Litterman optimization with CDaR constraints
7. Select the final top-10 portfolio and export to `outputs/final_weights.csv`
8. Run all 3 stress-test scenarios and print the resilience scorecard

### 3. Output Files

| Path | Contents |
| :--- | :--- |
| `outputs/final_weights.csv` | Ticker → weight mapping for the final 10-asset portfolio |
| `data/cache/universe_prices.csv` | Full KRW-converted price matrix |
| `data/cache/universe_volumes.csv` | Full volume matrix |

---

## Configuration Reference (`config.py`)

All parameters are centralized. Key values:

| Parameter | Default | Description |
| :--- | :--- | :--- |
| `VIX_KILLSWITCH` | 30.0 | VIX threshold for global risk-off |
| `FX_KILLSWITCH_LIMIT` | 0.05 | 5-day USD/KRW range cap |
| `BL_RISK_AVERSION` (δ) | 2.5 | Market risk-aversion for BL equilibrium |
| `BL_TAU` (τ) | 0.05 | Prior uncertainty scaling |
| `RM_METHOD` | `CVaR` | Risk measure for BL optimization |
| `CDAR_LIMIT` | 0.15 | Hard CDaR constraint (15%) |
| `MAX_ASSETS` | 10 | Final portfolio asset count |
| `MAX_WEIGHT_SINGLE` | 0.50 | Per-asset weight ceiling |
| `PRICE_START` | 2006-01-01 | Historical data start (covers 2008 GFC) |

---

## Project Structure

```
.
├── config.py                    # Single source of truth for all parameters
├── main.py                      # Pipeline orchestrator
├── data/
│   ├── universe.py              # Universe construction (Wikipedia + FDR)
│   └── loader.py                # Data fetching, caching, filtering, FX conversion
├── signals/
│   ├── composer.py              # 4-pillar signal aggregator + macro filters
│   ├── trend.py                 # MA alignment + envelope (vectorbt)
│   ├── fundamental.py           # FCF yield + EPS momentum (yfinance + Naver)
│   ├── options_skew.py          # Put-Call IV skew (yfinance options)
│   └── macro.py                 # VIX kill-switch + TIPS tilt + FX watchdog
├── portfolio/
│   ├── factor_loading.py        # FF5 OLS regression → idio variance + alpha
│   ├── constraints.py           # Liquidity caps with panic floor
│   └── selector.py              # Top-10 selection + CSV export
├── optimization/
│   ├── hrp.py                   # HRP equilibrium prior (riskfolio)
│   └── black_litterman.py       # BL model + CDaR-constrained UPI optimizer
├── backtest/
│   └── engine.py                # Multi-scenario vectorbt backtester
├── evaluation/
│   └── metrics.py               # MDD, Ulcer Index, Serenity & Calmar ratios
└── outputs/
    └── final_weights.csv        # Generated portfolio allocation
```

---

### Made by
- Byeong Jin Jeon (bjjeon0913@gmail.com)
- 떠들이 & 존버하고 나아가며 조율하는 투자의 군주 (https://www.youtube.com/@%EC%97%89%EB%93%9C%EB%A3%A8)
