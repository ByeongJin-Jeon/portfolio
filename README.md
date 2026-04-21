# Geopolitically Resilient Multi-Asset Allocation Engine

A **Resilience-First Quantitative Allocation Engine** engineered to maintain structural integrity during systemic market failures — including the 2008 Global Financial Crisis, the 2020 COVID Liquidity Crisis, and projected 2026 geopolitical instabilities.

The system integrates **Hierarchical Risk Parity (HRP)** as a Bayesian prior, **Black-Litterman (BL)** optimization with a proprietary **4-Pillar Alpha Engine**, and **Conditional Drawdown at Risk (CDaR)** constraints enforced by the `riskfolio-lib` solver. A layered macro kill-switch monitors VIX spikes, USD/KRW FX volatility, and TIPS real-rate dislocations to instantly rotate into defensive safe havens during systemic shocks.

---

## System Architecture

The engine executes a sequential 7-stage pipeline, each module importing exclusively from `config.py` as the single source of truth.

```
UniverseManager → DataLoader → SignalComposer → FactorLoading
       ↓               ↓              ↓               ↓
  800+ tickers   KRW-converted   4-Pillar Q-Views   Idio. Variance
                  price matrix                        (Omega matrix)
                                       ↓
                              HRP Prior Weights
                                       ↓
                         Black-Litterman Optimization
                         (CDaR ≤ 15%, Maximize UPI)
                                       ↓
                          Liquidity-Capped Selector
                             (Top 10 by weight)
                                       ↓
                      3-Scenario Resilience Backtest
                   (GFC 2008 / COVID 2020 / MIDEAST 2026)
```

---

## Module Reference

| Module | File(s) | Role |
| :--- | :--- | :--- |
| **Universe Construction** | `data/universe.py` | Scrapes S&P 500, NASDAQ-100, Dow Jones from Wikipedia; KOSPI 200 via `FinanceDataReader`. Merges with Core & Defensive ETF lists from `config.py`. |
| **Data Ingestion** | `data/loader.py` | Fetches OHLCV in 50-ticker chunks via `yfinance`. KRX tickers are suffixed `.KS` for download then mapped back to numeric codes. Prices saved as `utf-8-sig` CSV to preserve Hangul. |
| **Currency Normalization** | `data/loader.py` | Downloads `USDKRW=X` and multiplies all non-KRX tickers by spot rate, so every asset is priced in KRW for fair cross-market comparison. |
| **Candidate Filtering** | `data/loader.py` | Computes a 60-day Sharpe-momentum score (`momentum / volatility`). Selects top-15 KR + top-15 US by score from the top-50 liquid names in each market, plus 20 cross-market wildcards, then appends all Core and Defensive ETFs. |
| **Signal Composition** | `signals/composer.py` | Orchestrates the 4-pillar alpha engine, applies macro filters, and hard-codes defensive ETF views based on kill-switch state. |
| **Trend Engine** | `signals/trend.py` | MA alignment across 5/22/60/182-day windows using `vectorbt`. Scores golden/dead crosses (+0.5 / -0.5) and ±20% envelope oversold/overbought conditions (±1.0). |
| **Fundamental Engine** | `signals/fundamental.py` | US: FCF yield (`freeCashflow / enterpriseValue > 3%`) and EPS revision momentum via `yfinance`. KR: Operating profit yield scraped from Naver Finance HTML (`영업이익 / marketCap > 5%`). |
| **Idiosyncratic Alpha Engine** | `portfolio/factor_loading.py` | OLS regression against Fama-French 5-Factor daily data (`pandas_datareader`). Assets with positive mean residuals over the past 20 days receive a `+1.0` alpha view; negative mean → `-1.0`. The residual variance populates the **Omega uncertainty matrix** for Black-Litterman. |
| **Options Skew Engine** | `signals/options_skew.py` | Calculates OTM Put IV minus OTM Call IV from the nearest expiration chain (`yfinance`). Skew > 0.10 → bearish view (-1.0); skew < -0.05 → bullish view (+1.0). KR assets use EWY as a market-wide proxy. |
| **Macro Kill-Switch** | `signals/macro.py` | Monitors `^VIX` (kill-switch ≥ 30, confidence scalar above VIX 20) and `TIP` ETF (real-rate spike if daily drop > 1%). Applies quality tilt when real rates spike, using a dynamic KRX sector map built from `FinanceDataReader`. |
| **FX Kill-Switch** | `signals/composer.py` | Computes 5-day `(max/min − 1)` range of `USDKRW=X`. If > 5%, zeroes all KRX-side Q-views and routes capital to dollar-denominated assets. |
| **HRP Prior** | `optimization/hrp.py` | Runs `riskfolio-lib` HRP with Ward linkage and Pearson correlation-distance. This mean-estimation-free prior is robust to the noise of geopolitical regimes. |
| **Black-Litterman Optimizer** | `optimization/black_litterman.py` | Combines HRP prior, 4-pillar Q-views, and Omega from idiosyncratic variance. Optimizes for **max Ulcer Performance Index (UPI)** (`obj='Sharpe'`, `rm='CVaR'`) subject to CDaR ≤ 15%. Falls back to MinRisk CDaR, then to bare HRP if the solver fails. |
| **Liquidity Constraints** | `portfolio/constraints.py` | Weight cap per asset = 1% daily participation × effective volume × avg price / portfolio value. Effective volume is `max(20-day avg, 10th-percentile panic floor)` to prevent the cap collapsing during a sell-off. |
| **Portfolio Selector** | `portfolio/selector.py` | Applies liquidity caps, selects top-10 assets by BL weight, renormalizes to sum = 1, and exports to `outputs/final_weights.csv`. |
| **Backtest Engine** | `backtest/engine.py` | `vectorbt` portfolio simulation with `target_percent` rebalancing, 0.1% commission. Runs all scenarios defined in `config.BACKTEST_SCENARIOS` and skips any window where no selected assets existed. |
| **Evaluation Metrics** | `evaluation/metrics.py` | Computes MDD, Ulcer Index (`√mean(drawdown²)`), Serenity Ratio (`annualized return / (UI × |MDD|)`), and Calmar Ratio from the `vectorbt` portfolio object. |

---

## The 4-Pillar Alpha Engine

Q-views are composed as a weighted sum of four independent signal pillars before being fed into the Black-Litterman model. Weights are configurable in `config.Q_WEIGHTS`.

| Pillar | Default Weight | Source | Logic |
| :--- | :---: | :--- | :--- |
| **Fundamental** | 40% | `yfinance`, Naver Finance | FCF yield + EPS revision momentum (US); operating profit yield (KR) |
| **Technical Trend** | 20% | `vectorbt` MA | 5/22/60/182-day alignment, golden/dead cross, ±20% envelope |
| **Idiosyncratic Alpha** | 20% | FF5 OLS residuals | Mean of 20-day residuals from Fama-French 5-factor regression |
| **Options Skew** | 20% | `yfinance` options chain | OTM Put IV − Call IV; EWY proxy for all KRX assets |

---

## Macro Risk Layers

Three independent kill-switches operate in the signal composition stage:

**1. Global VIX Kill-Switch** (`VIX_KILLSWITCH = 30`)
- If `^VIX ≥ 30`, all equity Q-views are zeroed and defensive ETF views are set to `+2.0`
- Confidence scalar: `1 + max(0, (VIX − 20) / 20)` inflates the Omega uncertainty matrix above VIX 20, widening asset view intervals

**2. KR FX Kill-Switch** (`FX_KILLSWITCH_LIMIT = 5%`)
- If the 5-day USD/KRW range exceeds 5%, all KRX-side Q-views are zeroed
- Capital is implicitly redirected to USD-denominated assets and SGOV/SOFR proxies

**3. TIPS Real-Rate Spike Tilt**
- If the `TIP` ETF falls more than 1% in a single day (real rates spiking), a **Quality Tilt** is applied
- Growth/Tech views are multiplied by 0.5; Value/Defensive views are multiplied by 1.5
- Sector classification is built dynamically: KRX sector keywords from `FinanceDataReader`; US sectors from `yfinance`

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
