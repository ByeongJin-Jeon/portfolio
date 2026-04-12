# Executive Summary: Geopolitically Resilient Multi-Asset Allocation Engine

This document outlines the architecture and implementation of a **Resilience-First Quantitative Allocation Engine**. Engineered to maintain structural integrity during systemic market failures—including the 2008 Global Financial Crisis, the 2020 Liquidity Crisis, and projected 2026 geopolitical instabilities—this system transitions beyond traditional 60/40 benchmarks. It integrates **Hierarchical Risk Parity (HRP)**, **Black-Litterman (BL)** optimization, and **Conditional Drawdown at Risk (CDaR)** constraints to provide a sophisticated defense against tail-risk events.

---

## Core Architecture & Methodology

The engine utilizes a modular multi-stage pipeline designed to filter systemic noise and enforce strict risk boundaries.

| Module | Functional Logic | Strategic Objective | Indicator |
| :--- | :--- | :--- | :---: |
| **Asset Selection** (`loader.py`) | Universe filtering via Volume and Quality Scores | Eliminates low-liquidity and high-volatility outliers. | 🟢 |
| **Structural Foundation** (`config.py`) | 12 Fundamental Beta ETFs (SPY, TLT, GLD, etc.) | Establishes a diversified baseline of global asset classes. | 🟢 |
| **Risk-Based Allocation** (`hrp.py`) | Hierarchical Risk Parity (HRP) | Uses machine learning clustering to diversify based on correlation structures. | 🟡 |
| **Tactical Overlay** (`composer.py`) | 3-day Moving Average & VIX/FX Kill-Switch | Provides momentum-based signals and macro-economic safety triggers. | 🔴 |
| **Optimization & Defense** (`black_litterman.py`) | BL + CDaR Constraints | Incorporates tactical views while enforcing a hard 15% maximum drawdown limit. | 🔴 |

---

## System Directory & Technical Schema

The repository is structured to separate data ingestion, signal processing, and mathematical optimization for maximum maintainability.

```text
📦 asset_dashboard_portfolio
 ┣ 📂 data/            # Ingestion: Scrapes US/KR equities; calculates Quality Scores.
 ┣ 📂 signals/         # Tactics: Computes MA trends and VIX/FX volatility triggers.
 ┣ 📂 portfolio/       # Risk Analytics: Extracts Fama-French residuals and liquidity caps.
 ┣ 📂 optimization/    # Logic: HRP clustering and Black-Litterman/CDaR weight optimization.
 ┣ 📂 backtest/        # Simulation: VectorBT-powered stress tests across historical crises.
 ┣ 📂 evaluation/      # Metrics: Analysis of MDD, Ulcer Index, and Serenity Ratios.
 ┣ 📜 config.py        # Parameters: Definition of ETF pools and crisis simulation dates.
 ┗ 📜 main.py          # Orchestration: Execute the full end-to-end allocation pipeline.
```

---

## Implementation Protocol

To deploy the engine, ensure the local environment meets the requirements specified in the documentation.

### 1. Environment Configuration
Install the necessary quantitative libraries and dependencies:
```bash
pip install -r requirements.txt
```

### 2. Execution of the Allocation Pipeline
Initialize the primary orchestrator to perform data caching, HRP-BL optimization, and weight generation:
```bash
python main.py
```
Upon completion, the system exports the **Optimal Asset Weights** to `outputs/final_weights.csv` and generates a comprehensive performance report within the terminal interface.

---

## Stress-Testing Framework (Systemic Resilience)

The engine's efficacy is validated against three distinct "Black Swan" archetypes to ensure capital preservation:

1.  **Systemic Financial Shock (2008 GFC):** Validates performance during credit contractions and banking sector collapses.
2.  **Exogenous Liquidity Shock (2020 COVID-19):** Analyzes the engine’s response to rapid demand evaporation and unprecedented volatility spikes.
3.  **Geopolitical Supply Shock (2026 Projection):** Simulates a Middle Eastern conflict scenario characterized by energy price surges and stagflationary pressures.

Portfolios that maintain stability across these three vectors are classified as **Geopolitically Resilient Assets**.

---
### Made by
- Byeong Jin Jeon(bjjeon0913@gmail.com)
- 떠들이(https://www.youtube.com/@%EC%97%89%EB%93%9C%EB%A3%A8)