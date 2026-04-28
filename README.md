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
| **Data Ingestion** | `data/loader.py` | Fetches OHLCV via `yfinance`. Features **Local Cache Support** (`USE_CACHE_DATA`) to bypass redundant downloads. Prices converted to KRW with automated FX handling. |
| **Signal Composition** | `signals/composer.py` | Orchestrates the **13-Factor Alpha Engine**. Includes **Time-Machine Mode** and **Quality Tilt** logic during macro stress events. |
| **Trend Engine** | `signals/trend.py` | Uses yesterday's data (`shift(1)`) to compute **Minervini QM Scoring**, 6M Momentum, Volume/Price CV, Upside Potential, and the **Cash Flow Per Share (CPS) Trend Line**. |
| **Fundamental Engine** | `signals/fundamental.py` | **Hybrid KR Engine**: Integrates **DART API** (via `OpenDartReader`) and Naver Finance for deep KR fundamental coverage (Equity, NI, OP). Features daily local caching of views. |
| **Idiosyncratic Alpha** | `portfolio/factor_loading.py` | OLS regression against Fama-French 5-Factor daily data. Assets with positive residuals receive alpha views; residual variance populates the **Omega matrix**. |
| **Black-Litterman Optimizer** | `optimization/black_litterman.py` | Combines HRP prior, 13-factor Q-views, and Omega. Optimizes for **max Ulcer Performance Index (UPI)** subject to CDaR ≤ 15%. |
| **Backtest Engine** | `backtest/engine.py` | **Walk-Forward Controller**. Executes monthly rebalancing on actual last trading days. Re-filters candidates at every step to eliminate survival bias. |
| **Evaluation Metrics** | `evaluation/metrics.py` | Computes MDD, Ulcer Index (`√mean(drawdown²)`), Serenity Ratio, and Calmar Ratio from the `vectorbt` portfolio object. |

---

## The Walk-Forward "Time Machine"

To ensure the engine's resilience is empirically valid, the backtest engine (`backtest/engine.py`) operates under a strict **Walk-Forward Protocol**:

1. **Monthly Rebalancing**: Steps through time using actual end-of-month trading dates.
2. **Dynamic Candidate Filtering**: At each rebalance step, the system re-calculates momentum leaders from the full universe using only data available *then*.
3. **Point-in-Time Data**: The entire optimization pipeline (`my_quant_strategy`) is called using ONLY `prices.loc[:current_date]`.
4. **Time-Machine Mode**: In `signals/composer.py`, the system detects if `current_date` is in the past. If so, it bypasses live-only signals and uses neutral priors.
5. **Liquidity Realism**: Weight caps are recalculated at every step based on the rolling 20-day volume *at that specific point in time*.

---

## The 13-Factor Alpha Engine

Q-views are composed as a weighted sum of four independent signal pillars. The **Fundamental Pillar** now uses a high-fidelity hybrid engine for Korean assets.

| Pillar | Default Weight | Key Sub-Factors |
| :--- | :---: | :--- |
| **Fundamental** | 40% | **KRX**: DART API + Naver Crawler (Equity, OP, NI). **US**: yfinance. 8 factors including Innovative ROE and FCF Yield. |
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
- **Quality Tilt**: During volatility spikes, the engine applies a multiplier to quality-linked fundamental factors.
- Confidence scalar: `1 + max(0, (VIX − 20) / 20)` inflates the Omega uncertainty matrix, widening asset view intervals.

**2. KR FX Kill-Switch** (`FX_KILLSWITCH_LIMIT = 5%`)
- If the 5-day USD/KRW range exceeds 5%, all KRX-side Q-views are zeroed.
- Capital is implicitly redirected to USD-denominated assets.

**3. Risk-On vs. Risk-Off Tactical Tilt**
- **Risk-On (Kill-Switch Off)**: Defensive ETFs are penalized with a `-2.0` view.
- **Risk-Off (Kill-Switch On)**: Stocks are penalized (`-1.0`) while Defensive ETFs are boosted (`+2.0`).

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
- Final selection: top 10 assets by weight (`MAX_ASSETS`). Zero-weight assets are automatically pruned from export.

---

## Setup & Execution

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Key libraries: `yfinance`, `OpenDartReader`, `FinanceDataReader`, `riskfolio-lib`, `vectorbt`, `statsmodels`.

### 2. Configure API Keys

In `config.py`, set your **DART API Key** for KRX fundamental analysis:
```python
DART_API_KEY = "your_api_key_here"
USE_CACHE_DATA = True  # Enable to speed up repeated runs
```

### 3. Run the Pipeline

```bash
python main.py
```

The pipeline will:
1. Scan the full global universe (~800 tickers).
2. Fetch/Load price data (with local caching support).
3. Compute 4-pillar Q-views (using DART/Naver for KR assets with local view caching).
4. Run HRP → Black-Litterman optimization with CDaR constraints.
5. Export the final top-10 portfolio to `outputs/final_weights.csv`.
6. Run all stress-test scenarios with a rigorous walk-forward protocol.

---

## Output Files

| Path | Contents |
| :--- | :--- |
| `outputs/final_weights.csv` | Ticker → weight mapping for active positions only |
| `data/cache/universe_prices.csv` | Cached KRW-converted price matrix |
| `data/cache/fundamental_cache.csv` | Daily cached fundamental signal scores |

---

## Configuration Reference (`config.py`)

| Parameter | Default | Description |
| :--- | :--- | :--- |
| `USE_CACHE_DATA` | `True` | Use local CSV cache for prices/volumes |
| `DART_API_KEY` | `...` | API Key for South Korea's DART financial system |
| `VIX_KILLSWITCH` | 30.0 | VIX threshold for global risk-off |
| `FX_KILLSWITCH_LIMIT` | 0.05 | 5-day USD/KRW range cap |
| `CDAR_LIMIT` | 0.15 | Hard CDaR constraint (15%) |
| `MAX_ASSETS` | 10 | Final portfolio asset count |
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
