# Geopolitically Resilient Multi-Asset Allocation Engine — v2.0

A **Resilience-First Institutional Portfolio Engine** engineered for the KRX + global equity universe. v2.0 replaces the previous heuristic `HRP + BL + CDaR` stack with a mathematically coherent five-layer architecture: **IC-scaled fundamental alpha → orthogonalized factor risk model → constrained QP optimizer → ETF shelter sleeve → macro risk governor**.

---

## What Changed in v2.0

| Dimension | v1.x | v2.0 |
| :--- | :--- | :--- |
| **Alpha** | Mixed trend + fundamental Z-score views fed to BL | Pure IC-scaled fundamental alpha: `μᵢ = IC × σᵢ × zᵢ` (annualized decimal) |
| **Risk Model** | Sample covariance (no shrinkage) | EWMA (252d, halflife=63) + Ledoit-Wolf shrinkage + Gram-Schmidt factor orthogonalization |
| **Optimizer** | Riskfolio HCPortfolio + BL posterior | `cvxpy` mean-risk QP with CVaR & CDaR overlays (Rockafellar-Uryasev formulation) |
| **Safe Haven** | Hard-coded BL view overrides (`+2.0`) | ETF Shelter Sleeve — structural floor constraints tightened by macro regime |
| **Macro** | Binary kill-switches (VIX/FX) | Continuous macro risk governor → multipliers → sleeve/currency bound adjustments |
| **Alpha unit correctness** | Mixed Z-score + variance units (λᵣ ungrounded) | Dimensionally consistent: μ in annualized return units, λᵣ = 3.0 is interpretable CARA |
| **Factor multicollinearity** | Raw one-hot factor exposures | Gram-Schmidt orthogonalization in priority order: sleeve → country → sector → currency |
| **CVaR sign convention** | Inconsistent | Uniform loss convention throughout, consistent with Riskfolio-Lib |

---

## System Architecture

```
UniverseManager
      │
      ▼
DataLoader (OHLCV, USE_CACHE_DATA bypass)
      │  apply_currency_conversion (all prices → KRW base)
      │
      ▼
EligibilityFilter (candidate_frame, basic ADV / history filters)
      │
      ├──────────────────────────────────────────────┐
      ▼                                              ▼
MacroRiskGovernor                         FactorRiskModel
(VIX + FX regime → stress_regime)        (EWMA+LW Sigma, Gram-Schmidt B_orth, F)
      │                                              │
      ▼                                              │
Sleeve / CCY Bound Adjustments                       │
      │                                              │
      ├──────────────────────────────────────────────┤
      ▼                                              ▼
FundamentalAlphaEngine                    OptionsSkewEngine
(DART/Naver KR + yfinance US)             (OTM IV → uncertainty penalty u_i)
      │                                              │
      ▼                                              ▼
  μᵢ = IC × σᵢ × zᵢ               gamma_u × u_i  +  gamma_l × l_i
      │                                              │
      └──────────────── μ̃ (mu_tilde) ───────────────┘
                           │
                           ▼
              [Optional] Black-Litterman Posterior
                           │
                           ▼
              LiquidityParticipationCaps (κ = 10% ADV)
                           │
                           ▼
             cvxpy Mean-Risk QP Optimizer
             min  −μ̃'w + λᵣ w'Σw + λₕ‖w−wᵣₑf‖²
             s.t. Σwᵢ=1, box, sleeve, CCY, sector, country,
                  CVaR_α(w) ≤ L_cvar, CDaR_α(w) ≤ L_cdar
                           │
                    (fallback: HRP weights)
                           │
                           ▼
             PortfolioValidator + Reports
             (exposure, risk decomposition, alpha)
                           │
                           ▼
             ExecutionOrderPlanner (limit prices)
                           │
                           ▼
             HistoricalRiskReplay Backtest
             (GFC 2008 / COVID 2020 / MIDEAST 2026)
```

---

## 16-Step Pipeline (`main.py`)

| Step | Description |
| :---: | :--- |
| **1** | Load config + environment |
| **2** | Universe metadata (`UniverseManager`) |
| **3** | Fetch / cache price + volume data (`USE_CACHE_DATA` bypass) |
| **4** | Build candidate frame — eligibility filter (no trend signal used) |
| **5** | Apply currency conversion (all prices → KRW base) |
| **6** | Macro risk governor → `stress_regime`, adjusted sleeve & CCY bounds |
| **7** | Factor risk model: EWMA + Ledoit-Wolf + Gram-Schmidt orthogonalization |
| **8** | IC-scaled fundamental alpha (`μᵢ = IC × σᵢ × zᵢ`, equity only; ETFs get `μ=0`) |
| **9–10** | Assemble `μ̃ = μ − γ_u·u − γ_l·l` |
| **11** | Optional Black-Litterman posterior adjustment (`ENABLE_BLACK_LITTERMAN`) |
| **12** | Liquidity participation-rate caps (κ = 10% ADV) |
| **13** | Solve constrained mean-risk QP via `cvxpy` (CVaR + CDaR overlays) |
| **14** | Validate weights; generate exposure / risk / alpha reports |
| **15** | Execution order plan with limit buy prices |
| **16** | `HistoricalRiskReplay` backtest across all scenarios |

---

## Module Reference

| Module | File(s) | Role |
| :--- | :--- | :--- |
| **Universe Construction** | `data/universe.py` | Scrapes S&P 500, NASDAQ-100, Dow Jones from Wikipedia; KOSPI 200 via `FinanceDataReader`. Annotates each ticker with `sleeve`, `country`, `sector`, `trading_currency`, `is_etf_shelter`. |
| **Data Ingestion** | `data/loader.py` | Fetches OHLCV via `yfinance`. Local cache support (`USE_CACHE_DATA`). Prices converted to KRW base. Computes ADV for eligibility and liquidity caps. |
| **Macro Risk Governor** | `signals/macro.py` | Fetches live VIX + USD/KRW. Classifies `stress_regime` ∈ {`normal`, `elevated`, `stress`}. Produces multipliers that tighten safe-haven sleeve floors and CCY bounds. |
| **Fundamental Alpha** | `signals/fundamental.py` | **Hybrid KR Engine**: DART API (`OpenDartReader`) + Naver Finance for KRX equities; `yfinance` for US equities. 4-pillar Z-scores → IC scaling → `μᵢ` in annualized return units. Daily local caching. |
| **Uncertainty Penalty** | `signals/options_skew.py` | OTM Put IV − Call IV → `uᵢ` penalty term. Penalizes assets with elevated tail-risk pricing. ETF shelters receive `u=0`. |
| **Signal Assembler** | `signals/composer.py` | Assembles `μ̃ = μ − γ_u·u − γ_l·l`. Calls macro governor for constraint adjustments. No trend signals, no BL view composition, no defensive overrides. |
| **Factor Risk Model** | `portfolio/factor_loading.py` | Builds one-hot exposure matrix B. Gram-Schmidt orthogonalization (sleeve → country → sector → currency). EWMA factor covariance F + Ledoit-Wolf shrinkage. Specific risk floor `D_ii ≥ 1e-4`. Total: `Σ = B_orth F B_orth' + D`. |
| **QP Optimizer** | `optimization/mean_risk.py` | `cvxpy` solver. Rockafellar-Uryasev CVaR/CDaR constraints (loss convention). Falls back to HRP on solver failure. |
| **HRP Fallback** | `optimization/hrp.py` | Riskfolio `HCPortfolio`, Ward linkage, Pearson distance. Used as fallback when QP is infeasible and as `w_ref`. |
| **Optional BL** | `optimization/black_litterman.py` | Analyst view overlay. Disabled by default (`ENABLE_BLACK_LITTERMAN = False`). |
| **Portfolio Constraints** | `portfolio/constraints.py` | Builds all `cvxpy` constraint objects: box, sleeve, CCY, sector, country, liquidity participation caps. |
| **Portfolio Reports** | `portfolio/selector.py` | Weight validation, exposure report (sleeve/country/sector/CCY), risk decomposition, alpha attribution. |
| **Execution Planner** | `portfolio/execution.py` | Generates limit buy prices using ATR-based Chandelier logic anchored to yesterday's close (`shift(1)`). |
| **Backtest Engine** | `backtest/engine.py` | `HistoricalRiskReplay`: applies static optimized weights to historical price windows. `SnapshotWalkForward`: forward-only replay using stored decision snapshots. |
| **Evaluation Metrics** | `evaluation/metrics.py` | MDD, Ulcer Index (`√mean(DD²)`), Serenity Ratio, Calmar Ratio from `vectorbt` portfolio objects. |

---

## Alpha Engine — 4-Pillar Fundamental Model

All alphas are computed cross-sectionally, Z-scored, and then IC-scaled into annualized return units. **ETF shelter assets receive `μ = 0` by design** — they enter the portfolio purely via sleeve floor constraints, not alpha competition.

| Pillar | Weight | Key Sub-Factors |
| :--- | :---: | :--- |
| **Valuation** | 35% | Earnings Yield, FCF Yield, Operating Cash Yield, Book-to-Price |
| **Quality / Profitability** | 25% | Gross Profit-to-Assets, ROE, EBITDA Interest Coverage |
| **Balance Sheet Health** | 25% | Debt-to-Equity, Current Ratio, Cash-to-Assets |
| **Capital Discipline** | 15% | Capex-to-OCF, R&D-to-Revenue |

### IC Scaling (Grinold-Kahn)

```
μᵢ = IC × σᵢ × zᵢ
```

- `IC = 0.04` (assumed; calibrate via cross-validation as snapshots accumulate in `outputs/snapshots/`)
- `σᵢ` = annualized specific risk from the factor model
- `zᵢ` = cross-sectional composite Z-score

This ensures `μᵢ` is dimensionally consistent with `w'Σw` in the QP objective, making `λᵣ = 3.0` an interpretable CARA risk-aversion coefficient.

---

## Factor Risk Model

```
Σ = B_orth × F × B_orth' + D
```

| Component | Specification |
| :--- | :--- |
| **B_orth** | One-hot exposures Gram-Schmidt orthogonalized in priority: `sleeve → country → sector → currency` |
| **F** | Factor return covariance, EWMA window=252d, halflife=63d, Ledoit-Wolf shrinkage |
| **D** | Diagonal specific risk, floor `D_ii ≥ 1e-4` |

Gram-Schmidt orthogonalization removes multicollinearity between factor groups. Higher-priority groups (sleeve, country) are projected out of lower-priority columns (sector, currency) before estimating factor covariance.

---

## ETF Shelter Architecture

Safe-haven ETFs are treated as a **structural sleeve**, not alpha bets. They are excluded from fundamental scoring and receive `μ = 0`. Sleeve floors are enforced as hard QP constraints and are tightened by the macro risk governor under stress.

**Shelter Tickers** (`config.py`):
```
US:  TLT, IEF, SGOV, GLD, DBC
KR:  114260.KS (KODEX 국채10년), 148070.KS, 456880.KS, 069500.KS, 139260.KS
```

**Sleeve bounds** (base → tightened under stress):

| Sleeve | Base Min | Base Max | Under Stress (floor +) |
| :--- | :---: | :---: | :--- |
| `global_equity` | 20% | 80% | — |
| `safe_haven_bond` | 5% | 40% | +5% (elevated), +10% (stress) |
| `cash` | 5% | 30% | +5% (elevated/FX), +10% (stress) |
| `safe_haven_commodity` | 0% | 15% | +5% (stress) |
| `commodity` | 0% | 15% | — |
| `equity_index` | 0% | 20% | — |

---

## Macro Risk Governor

The macro governor runs at Step 6 and produces constraint multipliers that adjust all sleeve and CCY bounds before the QP is built. It **does not inject directional alpha views**.

| Regime | Trigger | Effect |
| :--- | :--- | :--- |
| `normal` | VIX < 20 | Base sleeve + CCY bounds |
| `elevated` | 20 ≤ VIX < 30 | Safe-haven bond floor +5%, Cash floor +5% |
| `stress` | VIX ≥ 30 | Safe-haven bond floor +10%, Cash floor +10%, Commodity floor +5% |
| `fx_stress` | 5d USD/KRW range ≥ 5% | Cash floor +5% (regardless of VIX regime) |

---

## Optimization Stack

```
μ̃ = μ − γ_u × u − γ_l × l
           │
           ▼
cvxpy QP:
  minimize  −μ̃'w + λᵣ·w'Σw + λₕ·‖w − wᵣₑf‖²
  subject to:
    Σwᵢ = 1
    MIN_WEIGHT ≤ wᵢ ≤ min(MAX_WEIGHT_SINGLE, liq_cap_i)
    sleeve bounds  (macro-adjusted)
    CCY bounds:    30% ≤ w_USD ≤ 70%,  30% ≤ w_KRW ≤ 70%
    sector cap:    w_s ≤ 25%
    country cap:   w_c ≤ 70%
    CVaR_0.05(w) ≤ L_cvar = 20%    (Rockafellar-Uryasev, loss convention)
    CDaR_0.05(w) ≤ L_cdar = 30%    (Rockafellar-Uryasev, loss convention)
           │
     (solver fails)
           │
           ▼
     HRP fallback (Ward / Pearson, riskfolio)
```

**Key optimizer parameters:**

| Parameter | Value | Meaning |
| :--- | :---: | :--- |
| `lambda_r` | 3.0 | CARA risk aversion (interpretable after IC scaling) |
| `lambda_h` | 0.25 | Holdings-stability regularizer (turnover control) |
| `gamma_u` | 0.50 | Options-skew uncertainty penalty weight |
| `gamma_l` | 0.25 | Liquidity penalty weight |
| `kappa` | 10% | Max participation rate relative to 20d ADV |

---

## Backtest Engine

Two backtest modes are available:

**1. `HistoricalRiskReplay`** (production-ready)
Applies the current optimized static weights to historical price windows. Fully valid because no future prices are used.

**2. `SnapshotWalkForward`** (future capability)
Replays the full alpha model across time using fundamental snapshots stored in `outputs/snapshots/`. Requires accumulated historical snapshots — not yet valid for early runs.

**Scenario windows:**

| Scenario | Window |
| :--- | :--- |
| GFC 2008 | 2007-07-01 → 2009-06-30 |
| COVID 2020 | 2019-10-01 → 2021-03-31 |
| MIDEAST 2026 | 2025-10-01 → present |

---

## Setup & Execution

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Key libraries: `yfinance`, `OpenDartReader`, `FinanceDataReader`, `cvxpy`, `riskfolio-lib`, `vectorbt`, `scikit-learn`, `statsmodels`.

### 2. Configure API Keys

In `config.py`, set your **DART API Key** for KRX fundamental analysis:

```python
DART_API_KEY   = "your_dart_api_key_here"
USE_CACHE_DATA = True   # bypass repeated downloads
```

### 3. Run the Pipeline

```bash
python main.py
```

The pipeline will:
1. Build full universe metadata (~800 tickers).
2. Fetch or load cached OHLCV data.
3. Classify macro regime (VIX + FX) and adjust sleeve/CCY bounds.
4. Build the EWMA + Ledoit-Wolf + Gram-Schmidt factor risk model.
5. Compute IC-scaled fundamental alpha (DART/Naver for KR; yfinance for US).
6. Solve the constrained mean-risk QP with CVaR/CDaR overlays.
7. Export the final portfolio, alpha report, and execution plan.
8. Run stress-test scenario backtests.

---

## Output Files

| Path | Contents |
| :--- | :--- |
| `outputs/final_weights.csv` | Ticker → weight mapping for active positions |
| `outputs/alpha_report.csv` | Per-asset `mu`, `mu_tilde`, `u`, `l`, composite Z-score |
| `outputs/exposure_sleeve.csv` | Sleeve-level weight exposure |
| `outputs/exposure_country.csv` | Country-level weight exposure |
| `outputs/exposure_sector.csv` | Sector-level weight exposure |
| `outputs/execution_plan.csv` | Limit buy prices (ATR-based Chandelier, yesterday's data) |
| `data/cache/universe_prices.csv` | Cached KRW-converted price matrix |
| `data/cache/universe_volumes.csv` | Cached volume matrix |
| `data/cache/fundamental_cache.csv` | Daily cached fundamental signal scores |
| `outputs/snapshots/` | Per-run decision snapshots (for future walk-forward replay) |

---

## Configuration Reference (`config.py`)

| Parameter | Default | Description |
| :--- | :--- | :--- |
| `USE_CACHE_DATA` | `True` | Load prices from local CSV cache |
| `DART_API_KEY` | `...` | API Key for South Korea's DART system |
| `IC_INITIAL` | `0.04` | Assumed information coefficient for IC scaling |
| `ALPHA_WEIGHTS` | `{val:0.35, qual:0.25, bs:0.25, cd:0.15}` | 4-pillar composite score weights |
| `COVARIANCE_WINDOW` | `252` | Rolling window for factor covariance (trading days) |
| `EWMA_HALFLIFE` | `63` | EWMA halflife for factor return weighting |
| `LEDOIT_WOLF_SHRINKAGE` | `True` | Apply Ledoit-Wolf shrinkage to factor covariance |
| `FACTOR_PRIORITY` | `[sleeve, country, sector, currency]` | Gram-Schmidt orthogonalization order |
| `OPTIMIZER_RISK_AVERSION` | `3.0` | CARA `λᵣ` (interpretable in annualized return units) |
| `OPTIMIZER_HOLDING_REG` | `0.25` | Turnover regularizer `λₕ` |
| `UNCERTAINTY_PENALTY` | `0.50` | Options-skew penalty weight `γ_u` |
| `LIQUIDITY_PENALTY` | `0.25` | Liquidity penalty weight `γ_l` |
| `CVAR_ALPHA` | `0.05` | CVaR tail probability |
| `CVAR_LIMIT` | `0.20` | Max expected tail loss (loss convention) |
| `CDAR_LIMIT` | `0.30` | Max conditional drawdown (loss convention) |
| `MAX_WEIGHT_SINGLE` | `0.10` | Per-asset weight ceiling |
| `MAX_WEIGHT_SECTOR` | `0.25` | Sector weight ceiling |
| `MAX_WEIGHT_COUNTRY` | `0.70` | Country weight ceiling |
| `MAX_ASSETS` | `20` | Max portfolio positions |
| `MAX_PARTICIPATION_RATE` | `0.10` | Max fraction of 20d ADV (`κ`) |
| `ENABLE_BLACK_LITTERMAN` | `False` | Toggle analyst BL view overlay |
| `BACKTEST_ENABLE` | `True` | Run historical risk replay after optimization |
| `PRICE_START` | `2006-01-01` | Historical data start (covers 2008 GFC) |

---

## Project Structure

```
.
├── config.py                    # Single source of truth for all parameters
├── main.py                      # 16-step pipeline orchestrator
├── data/
│   ├── universe.py              # Universe construction + metadata (sleeve/country/sector/CCY)
│   └── loader.py                # OHLCV fetch, cache, eligibility filter, FX conversion, ADV
├── signals/
│   ├── composer.py              # mu_tilde assembler + macro constraint dispatcher
│   ├── fundamental.py           # 4-pillar IC-scaled alpha (DART/Naver KR + yfinance US)
│   ├── options_skew.py          # OTM IV skew → uncertainty penalty u_i
│   ├── macro.py                 # VIX + FX regime → stress_regime + constraint multipliers
│   └── trend.py                 # (legacy — not used in production alpha pipeline)
├── portfolio/
│   ├── factor_loading.py        # EWMA + LW + Gram-Schmidt factor risk model
│   ├── constraints.py           # cvxpy constraint builder (sleeve, CCY, sector, country, liq)
│   ├── selector.py              # Validation + exposure / risk / alpha reports + CSV export
│   └── execution.py             # ATR-based limit price planner (Chandelier, shift(1))
├── optimization/
│   ├── mean_risk.py             # Primary cvxpy mean-risk QP (CVaR + CDaR overlays)
│   ├── hrp.py                   # HRP fallback (riskfolio, Ward / Pearson)
│   └── black_litterman.py       # Optional BL posterior adjustment
├── backtest/
│   └── engine.py                # HistoricalRiskReplay + SnapshotWalkForward
├── evaluation/
│   └── metrics.py               # MDD, Ulcer Index, Serenity & Calmar ratios
└── outputs/
    ├── final_weights.csv
    ├── alpha_report.csv
    ├── execution_plan.csv
    └── snapshots/               # Per-run decision snapshots for walk-forward
```

---

### Made by
- Byeong Jin Jeon (bjjeon0913@gmail.com)
- 떠들이 & 존버하고 나아가며 조율하는 투자의 군주 (https://www.youtube.com/@%EC%97%89%EB%93%9C%EB%A3%A8)

