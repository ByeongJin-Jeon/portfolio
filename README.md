# Geopolitically Resilient Multi-Asset Allocation Engine

This document outlines the architecture and implementation of a **Resilience-First Quantitative Allocation Engine**. Engineered to maintain structural integrity during systemic market failures—including the 2008 Global Financial Crisis, the 2020 Liquidity Crisis, and projected 2026 geopolitical instabilities—this system transitions beyond traditional 60/40 benchmarks. 

It integrates **Hierarchical Risk Parity (HRP)**, **Black-Litterman (BL)** optimization, and **Conditional Drawdown at Risk (CDaR)** constraints, supercharged by a proprietary **4-Pillar Alpha Engine** to provide a sophisticated defense against tail-risk events.

---

## Core Architecture & Methodology

The engine utilizes a modular multi-stage pipeline designed to filter systemic noise, track smart money, and enforce strict risk boundaries.

| Module | Functional Logic | Strategic Objective | Indicator |
| :--- | :--- | :--- | :---: |
| **Asset Selection** | Universe filtering via Volume and FX conversion | Eliminates low-liquidity outliers and standardizes KRW/USD pricing. | 🟢 |
| **Structural Foundation** | Core Beta ETFs + Top KOSPI/US Equities | Establishes a diversified baseline of global asset classes. | 🟢 |
| **Risk-Based Allocation** | Hierarchical Risk Parity (HRP) | Uses machine learning clustering to diversify based on correlation structures (Equilibrium Prior). | 🟡 |
| **Tactical Overlay** | **The 4-Pillar Alpha Engine** | Multi-dimensional alpha generation for Black-Litterman Q-Views. | 🟡 |
| **Macro Kill-Switch** | VIX Spike & FX Volatility (USD/KRW) | Instantly liquidates risk assets into safe havens during systemic shocks. | 🔴 |

---

## The 4-Pillar Alpha Engine (Black-Litterman Q-Views)

Traditional trend-following is a lagging indicator. This engine synthesizes four independent data dimensions to predict price action before it occurs, dynamically feeding the Black-Litterman model:

1. **Fundamental Engine (Weight: 40%) - *The Smart Money Tracker***
   - **Earnings Momentum:** Captures short-term explosive upside by tracking recent EPS estimate revisions by analysts.
   - **FCF Yield Defense:** Screens for a Free Cash Flow Yield > 5%, identifying companies with the actual cash power to defend their stock price (via buybacks/dividends) during market crashes.

2. **Idiosyncratic Alpha Engine (Weight: 20%) - *The Independent Ascender***
   - Extracts residual momentum unexplained by the **Fama-French 5-Factor Model**. It identifies assets that possess inherent upward momentum independent of broader market beta or macro headwinds.

3. **Options Skew Engine (Weight: 20%) - *The Derivative Bloodhound***
   - Analyzes Put-Call Implied Volatility (IV) Skew. By detecting when institutional investors overpay for Out-of-the-Money (OTM) put options, the engine identifies asymmetric downside panic and hedges positions proactively.

4. **Technical Trend Engine (Weight: 20%) - *The Momentum Aligner***
   - Utilizes multi-timeframe Moving Average alignment (5/22/60/182) and Mean Reversion Envelopes to confirm the final trajectory.

---

## Implementation Protocol

To deploy the engine, ensure the local environment meets the requirements specified in the documentation.

### 1. Environment Configuration
Install the necessary quantitative libraries and dependencies:
```bash
pip install -r requirements.txt
```

### 2. Execution of the Allocation Pipeline
Initialize the primary orchestrator to perform data caching, multi-engine signal generation, and HRP-BL optimization:
```bash
python main.py
```
Upon completion, the system exports the **Optimal Asset Weights** to `outputs/final_weights.csv` and generates a comprehensive performance report across historical and simulated Black Swan scenarios within the terminal interface.

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
- 떠들이 & 존버하고 나아가며 조율하는 투자의 군주(https://www.youtube.com/@%EC%97%89%EB%93%9C%EB%A3%A8)