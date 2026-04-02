# **Technical Specification: Geopolitically Resilient Multi-Asset Allocation Engine**

## **1. Core Objective**
Historical crises (2008 GFC, 2020 COVID, 2026 Middle East) prove that correlation spikes render traditional diversification useless. This engine implements a **Resilience-First** approach using **Hierarchical Risk Parity (HRP)** for structural diversification and **Black-Litterman (BL)** with **CDaR optimization** for tactical alpha.

## **2. Technical Environment & Data Integrity**
* **Libraries:** `Riskfolio-Lib` (Optimization), `vectorbt` (Backtesting), `Pandas`, `NumPy`.
* **Korean Data Protocol:** * All scripts must use `# -*- coding: utf-8 -*-`.
    * Use `unicodedata.normalize('NFC', ...)` for Korean ticker matching.
    * Handle `utf-8-sig` for CSV I/O to preserve Hangul in Windows/macOS environments.

## **3. Phase 1: Feature Engineering (Technical & Macro)**
Generate signals that will serve as "Subjective Views" ($Q$) and "Confidence" ($\Omega$) in the BL model.

### **A. Multi-Timeframe Trend Signals**
* **Indicators:** 5-day, 22-day, 60-day, and 182-day Moving Averages (MA).
* **Envelope Filter:** 22-day MA with $\pm10\%$ bands.
* **Logic:** * **Full Bullish:** $5 > 22 > 60 > 182 \rightarrow$ High conviction positive view.
    * **Mean Reversion:** Price $> +10\%$ Upper Envelope $\rightarrow$ Overbought (Reduce $Q$ or $\Omega$).

### **B. Macro Risk Filters (McGee TAA)**
* **VIX Kill-Switch:** If $VIX > 25$, reduce total equity beta and rotate to `ACE SOFR ETF`.
* **TIPS Sensitivity:** Monitor 10Y TIPS. If real rates spike, tilt away from **Growth** and toward **Quality (QUAL)** factors.

## **4. Phase 2: The Optimization Logic**

### **A. Step 1: Hierarchical Risk Parity (HRP)**
Use tree-clustering to isolate risk blocks (Energy, Tech, Defense, etc.) and prevent matrix inversion failure during high-correlation regimes.

### **B. Step 2: Black-Litterman (BL) Integration**
Combine HRP-derived weights (as equilibrium) with the Phase 1 tactical views.
* **Views ($Q$):** Based on MA alignment and geopolitical supply-chain risks (Energy/Agri overweight).
* **Confidence ($\Omega$):** Calculated based on the slope of 60-day MA and VIX levels.

### **C. Step 3: CDaR Optimization**
Maximize the **Ulcer Performance Index (UPI)** subject to a **CDaR (Conditional Drawdown at Risk)** constraint of $15\%$.
* **Objective Function:**
$$\max \frac{R_p - R_f}{UI} \quad \text{s.t.} \quad CDaR \le 0.15$$

## **5. Phase 3: Universe & Asset Classes**
The "Barbell" strategy combining KRX and US-listed instruments.

| Segment | Tickers (KRX / US) | Strategic Rationale |
| :--- | :--- | :--- |
| **Defensive Alpha (Quality & Defense)** | **Hanwha Aerospace (012450.KS)**, **LIG Nex1 (079550.KS)** / **Microsoft (MSFT)**, **Apple (AAPL)** | Captures geopolitical security premiums in KRX and high-ROE quality factor in US. |
| **Supply Chain (Energy & Agri)** | **HD Hyundai Heavy Industries (329180.KS)** / **Exxon Mobil (XOM)**, **Archer-Daniels-Midland (ADM)**, **Corteva (CTVA)** | Direct exposure to energy transport, upstream oil, and the "Energy-Agri Nexus". |
| **Safe Haven (Miners)** | **Korea Zinc (010130.KS)** / **Newmont (NEM)**, **Barrick Gold (GOLD)** | Equity-based proxies for physical gold; provides a "monetary shield" during fiat debasement. |
| **Core & Liquid Reserves** | **Samsung Electronics (005930.KS)** / **Johnson & Johnson (JNJ)**, **Procter & Gamble (PG)** | High-liquidity core holdings and low-beta consumer staples for drawdown protection. |

## **6. Phase 4: Performance Evaluation**
Backtest across 2008, 2020, and 2026 scenarios using `vectorbt`. Report the following metrics:
* **Serenity Ratio:** Holistic stress-free return.
* **Ulcer Index (UI):** Depth and duration of drawdowns.
* **Calmar Ratio:** Return vs. Maximum Drawdown (MDD).

---

### **💡 Prompting an AI (Claude/Gemini) for Code:**

> "Based on the **'Geopolitically Resilient Portfolio'** architecture defined in the Markdown above, please write the Python code. Specifically, implement the following four modules:
> 1. A function using `vectorbt` to generate signals based on **5/22/60/182-day Moving Average (MA) alignment (Golden Cross sequence)** and **22-day Envelopes**.
> 2. An optimization engine using `Riskfolio-Lib` that combines **HRP (Hierarchical Risk Parity) weights with Black-Litterman (BL) views** to **minimize CDaR (Conditional Drawdown at Risk)**.
> 3. A function to select **a maximum of 10 assets**, calculate their weights, and output the results to both the terminal and a CSV file.
> 4. A data loading utility featuring **UTF-8-SIG encoding and NFC normalization** for handling Korean stock names. Specifically, it must extract the **Top 200 KOSPI stocks by market cap** and components of the **S&P 500, NASDAQ, and Dow Jones** indices.


### **💡 Additional Logic to Emphasize (Prompt Extension)**

1. **Idiosyncratic Risk Handling**: "Since we are using individual stocks instead of ETFs, use the **HRP (Hierarchical Risk Parity)** feature in `Riskfolio-Lib` to remove correlation noise and allocate weights based on 'Risk Blocks'."
2. **Factor Loading**: "Include logic to link individual stock returns with the **Fama-French 5-Factor** model to calculate how much exposure each stock has to our target factors, such as 'Quality' or 'Value'."
3. **Liquidity Constraint**: "Individual stocks carry higher liquidity risk than ETFs. Add code to set a **Weight Constraint** based on the average trading volume of the last 20 days."


### **❓ Recommendation for Discussion**
When switching to individual stocks, signals from the **Moving Averages (5/22/60/182) and Envelopes ($\pm10\%$)** will trigger much more frequently than they would with ETFs. I recommend consulting with Claude/Gemini on how to adjust the **confidence levels (Omega matrix)** or weights when these signals are integrated as **Black-Litterman 'Views'**!