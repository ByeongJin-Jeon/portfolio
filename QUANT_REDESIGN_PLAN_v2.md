# Quant Redesign Plan (v2)

## Purpose

This document replaces the previous redesign note.

Its goal is to define a mathematically clear and market-accepted redesign path for this repository while preserving the main idea:

- resilience-first multi-asset allocation
- strong downside control
- explicit liquidity and exposure management
- no use of past price trends as alpha

The redesign target is not a heuristic score engine.
It is an institutional-style architecture:

- fundamental alpha model
- factor risk model
- constrained optimizer
- tail-risk and stress overlay
- execution and liquidity controls

This is much closer to real-market portfolio construction than the repo's current mixed `trend + BL + CDaR + overrides` stack.

**v2 amendments** address three mathematical correctness issues identified in design review (alpha unit inconsistency, factor multicollinearity, CVaR sign convention) and two implementation gaps (ETF shelter architecture, covariance estimation specification). These are documented in the section `Mathematical Correctness Requirements` and reflected throughout all relevant sections.

---

## Executive Conclusion

The current repo should **not** be evolved by tweaking the existing `HRP + BL + CDaR` implementation in place.

Instead, it should be restructured into:

1. **Expected return model**
2. **Risk model**
3. **Optimization engine**
4. **Stress and drawdown control**
5. **Execution layer**

This preserves the repo's strategic idea but replaces the current inconsistent implementation with a cleaner and more defensible workflow.

The main design principle is:

- **do not use past price or trend signals as alpha**
- **do use historical or estimated risk inputs for risk modeling**

That distinction is standard and mathematically defensible.

Three additional requirements are binding in v2:

- **alpha scores must be converted to return units before entering the optimizer** (IC scaling)
- **factor exposures must be orthogonalized before estimating factor covariance** (Gram-Schmidt hierarchy)
- **CVaR sign convention must be uniform and consistent with Riskfolio-Lib** (loss convention throughout)

---

## What Must Be Preserved From The Current Repo

The current repo has a valid strategic intent that should remain intact:

- resilience-first construction
- global multi-asset opportunity set
- explicit safe-haven sleeve
- liquidity-aware sizing
- scenario and downside awareness

These are worth preserving.

What should not be preserved is the current way they are implemented.

---

## Main Problems In The Current Implementation

## 1. The alpha engine is mixed with risk overlays

Current modules mix:

- trend and momentum
- macro state
- options skew
- fundamental quality
- FF residual alpha
- defensive overrides

into one view vector.

This is not clean model design.

Why this is a problem:

- expected return is being mixed with uncertainty
- macro regime flags are treated as directional asset alpha
- safe-haven sleeves are being hard-coded as score overrides
- options data is being treated as alpha rather than risk

This creates causal confusion and makes model interpretation weak.

## 2. `HRP + BL + CDaR` is used with inconsistent inputs

The mathematical objects are legitimate, but the implementation is not coherent:

- `HRP` prior comes from historical returns
- `BL` views come from mixed heuristic signals
- `Omega` partly comes from FF residual logic
- `CDaR` is treated as a core optimizer objective
- liquidity caps are applied post hoc

The problem is not that `HRP`, `BL`, or `CDaR` are bad.
The problem is that the repo is feeding them economically inconsistent inputs.

### Mathematical sub-issues within this block

These were identified in design review and are resolved in the `Mathematical Correctness Requirements` section.

**Sub-issue 2a: Alpha score dimensional inconsistency**

The optimizer objective mixes `mu_tilde' w` (dimensionless Z-score units) with `w' Sigma w` (return-variance units). These cannot be meaningfully subtracted. `lambda_r = 3.0` has no theoretical grounding unless `mu` is expressed in annualized return units. This is resolved by Grinold-Kahn IC scaling.

**Sub-issue 2b: Factor exposure multicollinearity**

One-hot encoding of country, sector, currency, and sleeve simultaneously produces collinear columns in `B`. A Korean tech stock loads on `country_KR = 1`, `sector_IT = 1`, `currency_KRW = 1`, and `sleeve_equity = 1` at the same time. Without orthogonalization, the factor covariance matrix `F` becomes ill-conditioned and `D` absorbs correlated variance that belongs in `F`. This is resolved by hierarchical Gram-Schmidt orthogonalization.

**Sub-issue 2c: CVaR sign convention ambiguity**

The original plan uses CVaR in return convention in some places and loss convention in others. Riskfolio-Lib (already used in this repo) follows the loss convention. Mixing conventions produces incorrect constraint direction. This is resolved by adopting the loss convention uniformly.

## 3. The KR/US allocation logic is not real currency-risk control

The current prefilter uses a hard 50/50 split by ticker count.

That is not a valid country or FX risk model.

Why this is flawed:

- count-based balancing ignores market value and weight
- country count is not currency exposure
- it can force capital into the weaker cross-section
- it can increase total risk under the guise of diversification

Real portfolio construction should use:

- currency exposure constraints
- country exposure limits
- issuer and sector caps

not equal ticker quotas.

## 4. The backtest discipline is overstated

The repo claims walk-forward discipline, but several signals are live-only:

- current fundamentals
- current options chain data
- current macro data fetched in live form

Therefore:

- price mechanics may be replayable
- full alpha logic is not historically validated in a true point-in-time sense

This must be stated clearly in the redesign.

## 5. Trend-based alpha violates the desired modeling standard

The user requirement is now clear:

- quant logic must not rely on past data or price trends as alpha

That rules out:

- moving average alignment
- envelope logic
- 6M return ranking
- FF residual return-based alpha
- breakout / technical timing logic

Those must leave the main alpha path.

---

## Design Principle

The redesign should follow a structure used widely in professional portfolio construction:

## Layer 1. Alpha

Use a current-state expected return model based on structural fundamentals.

## Layer 2. Risk

Use a formal risk model:

- covariance model
- ideally factor risk model
- country, sector, style, and currency exposures

## Layer 3. Optimization

Use explicit constrained optimization:

- maximize expected return or utility
- penalize risk
- enforce real-world constraints

## Layer 4. Tail-Risk Control

Use:

- CVaR or CDaR
- scenario testing
- stress tests

as constraints or evaluation layers, not as a substitute for the whole portfolio engine.

## Layer 5. Execution

Handle:

- liquidity
- trade sizing
- participation assumptions
- implementation realism

separately from alpha.

---

## Mathematical Correctness Requirements

This section documents three mathematical issues identified during design review. Each must be resolved before implementation begins. They are binding requirements, not suggestions.

---

### Requirement 1: Alpha Score Unit Conversion via IC Scaling

#### The Problem

The composite fundamental score:

```
z_i = beta_v * v_i + beta_q * q_i + beta_b * b_i + beta_d * d_i
```

is a dimensionless cross-sectional Z-score after normalization.

The optimizer objective:

```
J(w) = mu_tilde' w - lambda_r * w' Sigma w - lambda_h * ||w - w_ref||^2
```

contains `w' Sigma w` in annualized return-variance units (e.g., `0.04` for a 20% annual-vol portfolio). When `mu_tilde` is a dimensionless score, the subtraction is dimensionally inconsistent.

Concretely, the CARA mean-variance utility is:

```
J = E[r] - (lambda_r / 2) * Var[r]
```

This is only well-defined when `E[r]` and `Var[r]` are in the same return units. Setting `lambda_r = 3.0` is only theoretically grounded (as a risk aversion coefficient) when `mu` is expressed in annualized decimal return units. With dimensionless scores, `lambda_r` is an uncalibrated empirical knob with no interpretable magnitude.

#### The Fix: Grinold-Kahn IC Scaling

Convert the dimensionless composite score `z_i` to expected annualized excess return using:

```
mu_i = IC * sigma_i * z_i
```

where:

- `IC` is the Information Coefficient: cross-sectional Pearson correlation between `z_i` at time `t` and realized residual returns over a forward horizon, estimated empirically
- `sigma_i = sqrt(D_ii)` is the asset-specific residual risk from the factor model (annualized, decimal)
- `mu_i` is the resulting expected excess return in annualized decimal units

Typical IC values for fundamental signals:

- conservative estimate: `0.02`
- moderate estimate: `0.04`
- strong fundamental model: `0.06 - 0.07`

#### Initial IC Assumption

For the initial implementation, where no historical snapshot IC history is available, use:

```
IC_initial = 0.04
```

Document this as an assumed value, not a calibrated one. Update by cross-validation as decision snapshots accumulate.

#### Dependency: Risk Model Must Run First

`sigma_i` (from `D`) must be estimated by the factor risk model before IC scaling can be applied. The correct pipeline order is:

```
1. Estimate factor risk model  ->  B, F, D
2. Extract sigma_i = sqrt(D_ii)
3. Compute z_i from fundamental signals
4. Scale: mu_i = IC * sigma_i * z_i
5. Apply adjustments: mu_tilde_i = mu_i - gamma_u * u_i - gamma_l * l_i
6. Run optimizer with mu_tilde and Sigma
```

This dependency must be reflected in the main orchestration pipeline.

#### Effect on lambda_r

After IC scaling, `mu_i` is in annualized decimal return units. `lambda_r = 3.0` is now interpretable as a standard CARA risk aversion coefficient, implying the investor penalizes `1.5` units of variance per unit of excess return. This is a reasonable starting value for a moderately risk-averse institutional portfolio.

---

### Requirement 2: Factor Exposure Orthogonalization

#### The Problem

When `B` uses binary one-hot indicators for country, sector, currency, and sleeve simultaneously, each asset carries multiple active columns at once. A Korean technology stock has:

```
country_KR  = 1
sector_IT   = 1
currency_KRW = 1
sleeve_equity = 1
```

These columns are correlated by construction. This causes:

- the factor covariance matrix `F` to be ill-conditioned or rank-deficient
- the specific risk matrix `D` to absorb systematic covariance that belongs in `F`
- risk decomposition (country contribution, sector contribution, etc.) to be unstable and misleading

The Barra USE4 methodology explicitly addresses this with an orthogonalization step for style factors. The same principle applies here.

#### The Fix: Hierarchical Gram-Schmidt Orthogonalization

Define a priority hierarchy for factor groups:

```
Priority 1 (highest): Sleeve       (broadest classification)
Priority 2:           Country
Priority 3:           Sector
Priority 4 (lowest):  Currency     (most granular)
```

Orthogonalize each lower-priority factor column by projecting out all higher-priority columns using OLS residuals:

```
For each column b_k belonging to priority group p:
  b_k_ortho = b_k - B_higher * (B_higher' B_higher)^{-1} B_higher' b_k
```

where `B_higher` is the submatrix of all columns with priority < p.

#### Result

After orthogonalization:

- "Sector effect" captures sector variation net of country and sleeve effects
- "Currency effect" captures currency variation net of sector, country, and sleeve effects
- Factor covariance `F` is well-conditioned and interpretable
- Risk decomposition cleanly separates contributing sources

#### Required New Function

Add to `portfolio/factor_loading.py`:

```
orthogonalize_factor_exposures(B, priority_order) -> B_ortho
```

This must run before `estimate_factor_covariance` and `estimate_specific_risk`.

---

### Requirement 3: CVaR Sign Convention Uniformity

#### The Problem

There are two common conventions for CVaR:

- **Return convention**: `CVaR_alpha(r_p) = E[r_p | r_p < VaR_alpha]`  (negative number in bad scenarios)
- **Loss convention**: `CVaR_alpha = E[loss] = -E[r_p | r_p < VaR_alpha]`  (positive number, higher = worse)

The original plan writes the tail-risk constraint as:

```
CVaR_alpha(r_p) >= -L_cvar      # return convention
```

Riskfolio-Lib (already used in this repo) follows the **loss convention**. Mixing conventions in code produces incorrect constraint direction and is a silent error.

#### The Fix: Adopt Loss Convention Throughout

Use the loss convention uniformly in all sections, code, and documentation:

```
CVaR_alpha(w)  <= L_cvar     # maximum acceptable expected tail loss
CDaR_alpha(w)  <= L_cdar     # maximum acceptable conditional drawdown
```

where both `L_cvar` and `L_cdar` are positive scalars representing maximum tolerable loss fractions.

This aligns with Riskfolio-Lib's interface and eliminates sign ambiguity.

Apply this convention in all constraint specifications, stress-test reporting, and veto logic.

---

## Recommended Institutional Architecture

The redesigned repo should implement the following architecture.

### A. Fundamental Alpha Model

This is the expected return engine.

It should use **current-state** variables only, not past price trends.

**Scope: individual equity securities only.**

ETF assets (bond ETFs, commodity ETFs, cash ETFs, index ETFs) are excluded from this model. They are handled by the ETF Shelter Architecture (Section F).

#### Recommended alpha families

Use these as the main return signals:

- valuation
- profitability
- balance sheet strength
- earnings quality
- internal financing capacity
- dilution burden
- capital efficiency

#### Example feature set

Valuation:

- earnings yield
- free cash flow yield
- operating profit yield
- book-to-price as fallback

Profitability / quality:

- gross profitability to assets
- ROE or ROIC
- operating cash flow to net income
- operating margin

Balance sheet resilience:

- debt to equity
- net debt to EBITDA
- current ratio
- interest coverage
- cash to assets

Capital discipline:

- share issuance / dilution
- capex burden
- dividend coverage

#### Score-to-return conversion

Raw feature scores must be converted to expected return units via IC scaling before entering the optimizer:

```
mu_i = IC * sigma_i * z_i
```

See Mathematical Correctness Requirements, Requirement 1 for full specification.

#### Important rule

These features are alpha inputs only if they are treated as forecasts of medium-term cross-sectional return.

They should not be mixed with:

- VIX signals
- option skew
- country stress flags

Those belong to risk.

---

### B. Factor Risk Model

This becomes the mathematical backbone of the portfolio engine.

It replaces the current dependence on `HRP` as the core structural organizer.

#### Recommended exposures

The risk model should capture:

- country exposure
- currency exposure
- industry / sector exposure
- style exposures if available
- idiosyncratic risk

#### Practical phase-1 version

Implement a simplified factor model:

- one-hot country factors
- one-hot sector factors
- optional instrument-type factors
- optional duration / commodity sleeve factors
- residual specific risk estimate

This is already closer to institutional practice than `HRP` for the primary engine.

**Important:** One-hot factors must be orthogonalized before use. See Mathematical Correctness Requirements, Requirement 2.

#### Covariance Estimation Specification

All covariance and specific risk estimates must use the following parameters:

| Parameter | Value |
|---|---|
| Rolling window | 252 trading days |
| Weighting scheme | Exponentially weighted (EWMA), halflife = 63 days |
| Shrinkage | Ledoit-Wolf analytical shrinkage |

Apply this specification to:

- factor covariance matrix `F`: estimated from exponentially weighted factor return series, Ledoit-Wolf shrinkage applied
- specific risk diagonal `D`: estimated from exponentially weighted squared residual returns, minimum floor applied for numerical stability

**Implementation note:** `sklearn.covariance.LedoitWolf` assumes i.i.d. observations. When using EWMA, compute the weighted sample covariance manually (using `numpy` or `pandas.DataFrame.ewm().cov()`) and then apply the Ledoit-Wolf analytical shrinkage coefficient to it:

```
S_ewm    = exponentially_weighted_covariance(returns, halflife=63)
alpha_lw = ledoit_wolf_shrinkage_coefficient(returns)   # e.g., from sklearn internals or manual derivation
mu_target = np.trace(S_ewm) / N * np.eye(N)             # scaled identity target
S_lw     = (1 - alpha_lw) * S_ewm + alpha_lw * mu_target
```

#### Why this is better than current `HRP`

`HRP` is mathematically valid, but it is not the natural core when your main needs are:

- explicit country control
- explicit currency control
- explicit sector limits
- transparent decomposition of risk

Those are better handled by a factor risk model plus optimizer.

---

### C. Constrained Optimizer

The optimizer should maximize expected return subject to risk and implementation constraints.

**Scope:** The optimizer operates over the full asset universe including ETFs. ETF assets carry `mu_i = 0` (no fundamental alpha). Their sleeve floor constraints ensure minimum allocation independently of alpha.

#### Recommended objective

```
minimize  -mu_tilde' w + lambda_r * w' Sigma w + lambda_h * ||w - w_ref||^2
```

where `mu_tilde_i = mu_i - gamma_u * u_i - gamma_l * l_i` and all terms are dimensionally consistent after IC scaling.

#### Constraint set

The optimizer should include explicit constraints for:

- full investment
- long-only if required
- max single name weight
- max sector weight
- max country weight
- currency band constraints
- liquidity caps
- instrument sleeve minimum / maximum weights
- safe-haven sleeve rules

This is where the repo should express resilience cleanly.

---

### D. Tail-Risk Overlay

`CDaR` should not disappear.
It should be repositioned.

Use it as:

- a constraint
- a stress filter
- an evaluation metric
- a portfolio veto trigger

not as the sole core allocator.

This keeps the downside focus without forcing the entire portfolio design to depend on one historical drawdown statistic.

**CVaR and CDaR constraints use the loss convention throughout:**

```
CVaR_alpha(w) <= L_cvar
CDaR_alpha(w) <= L_cdar
```

See Mathematical Correctness Requirements, Requirement 3.

---

### E. Stress and Scenario Engine

The existing resilience idea should become more formal here.

Instead of putting crisis logic directly into alpha views, define:

- equity crash scenario
- KRW depreciation scenario
- duration shock
- commodity shock
- sector concentration shock

Portfolio outputs should then report:

- country exposure
- currency exposure
- factor exposure
- stress-test loss estimates

This is much more realistic than hard-coding defensive assets to `+2` or `-2`.

---

### F. ETF Shelter Architecture

This is a new component with no equivalent in the original repo.

#### Design principle

ETFs in this repo are not alpha-generating securities. They are pre-defined shelter instruments allocated when macro conditions or portfolio stress flags indicate the need for ballast. They are not scored by the fundamental alpha model.

Concretely:

- ETFs do **not** receive fundamental scores (`mu_ETF = 0` in the optimizer)
- ETFs are allocated by policy-defined sleeve constraints, not alpha rank
- ETF sleeve floors are tightened by the macro risk governor under stress conditions
- ETFs remain inside the total covariance matrix `Sigma` for risk estimation purposes

#### Designated shelter ETFs

| Asset | Type | Sleeve |
|---|---|---|
| `TLT`, `IEF` | US long/mid treasury | `bond` |
| `SGOV` | US ultra-short / cash | `cash` |
| `GLD` | Gold | `safe_haven_commodity` |
| `DBC` | Broad commodity | `commodity` |
| `114260.KS` | KR 3Y treasury (KODEX) | `bond` |
| `148070.KS` | KR 10Y treasury | `bond` |
| `456880.KS` | ACE SOFR / dollar cash ETF | `cash` |
| `069500.KS` | KODEX 200 (KR market beta) | `equity_index` |
| `139260.KS` | TIGER 200 IT (KR tech beta) | `equity_index` |

Equity index ETFs (`KODEX 200`, `TIGER 200 IT`) may receive a small positive floor to maintain market exposure but are not alpha-ranked individually.

#### Macro-conditioned sleeve floors

The macro risk governor (`signals/macro.py`) sets ETF sleeve floors as a function of macro state:

| Macro condition | ETF sleeve floor adjustment |
|---|---|
| Normal (VIX < 20) | Apply base sleeve minimums |
| Elevated (20 ≤ VIX < 30) | Increase `bond` and `cash` floors by `+0.05` |
| Stress (VIX ≥ 30) | Increase `bond`, `cash`, `safe_haven` floors by `+0.10`, reduce `equity_index` cap |
| FX stress (fx_vol ≥ 0.05) | Increase `cash_USD` floor, decrease `KRW` cap |

These adjustments are passed to `portfolio/constraints.py` as modified sleeve bounds, not as alpha signals.

#### Two-Stage Portfolio Assembly

Total portfolio weights are assembled in two logical stages even though the optimizer solves the problem jointly:

**Stage 1: Shelter allocation (policy-driven)**

- Macro state is determined
- Sleeve floor constraints for ETFs are set
- These appear as hard lower bounds in the optimizer: `w_ETF_i >= floor_ETF_i`

**Stage 2: Alpha allocation (model-driven)**

- Remaining capital flows to individual equity securities via the fundamental alpha model and QP optimizer
- ETF weights may exceed their floors if the optimizer finds them beneficial (they won't, since `mu_ETF = 0`, so in practice ETFs sit at their floor values unless the risk model finds them beneficial for variance reduction)

**Stage 3: Combine and validate**

- Optimizer returns unified weight vector over all assets
- Portfolio reporting separates shelter sleeve from alpha sleeve for attribution

---

## Role Of `HRP`, `BL`, And `CDaR` In The New Design

This section is the direct answer to whether the redesign should stem from the current algorithm.

## 1. HRP

### Recommendation

Do **not** use `HRP` as the main portfolio-construction engine.

### Reason

`HRP` is mathematically respectable, but it does not naturally express:

- country exposure constraints
- currency exposure budgets
- sector caps
- instrument sleeve policy
- safe-haven allocation rules

It is a better tool for:

- diversification overlays
- robustness comparisons
- fallback portfolio construction

### Best use in redesigned repo

Keep `HRP` only as:

- benchmark portfolio
- fallback allocator
- diversification diagnostic

not as the primary engine.

## 2. Black-Litterman

### Recommendation

Keep the **idea** of `BL`, but only if inputs are cleaned up.

### Reason

`BL` remains useful if the repo wants:

- equilibrium prior
- explicit subjective views
- mathematically consistent blending of prior and forecast

But current repo usage is weak because views are built from mixed and poorly separated sources.

### Best use in redesigned repo

Use `BL` only if:

- the prior is clearly defined
- the views come from the fundamental alpha model
- view uncertainty is tied to data quality and model confidence

That makes `BL` optional, not mandatory.

## 3. CDaR

### Recommendation

Retain `CDaR`, but demote it from "the main engine" to "tail-risk control layer."

### Reason

This preserves the resilience thesis while putting the optimizer on more standard footing.

### Best use in redesigned repo

Use `CDaR` as:

- constraint: `CDaR_alpha(w) <= L_cdar` (loss convention)
- risk report
- veto rule for final allocations

not the whole portfolio objective.

---

## Direct Answer To The "No Past Data" Requirement

This must be handled carefully.

There are two different meanings of "past data":

### A. Past data as alpha

This should be avoided in the main path.

So:

- no momentum alpha
- no trend alpha
- no moving-average alpha
- no return-based residual alpha

### B. Past data as risk estimation

This is still acceptable and necessary in professional portfolio construction.

Why:

- covariance needs estimation
- factor risk needs estimation
- specific risk needs estimation
- downside metrics like `CDaR` require path history

So the mathematically clean interpretation is:

- **do not use past price data to generate alpha**
- **do use historical or modeled data to estimate risk**

That preserves both rigor and practicality.

The covariance estimation specification (252-day EWMA with Ledoit-Wolf shrinkage) defined in Section B of Recommended Institutional Architecture governs all risk estimation uses of historical data.

---

## New Model Specification

The target model should be written in four objects.

## 1. Alpha Vector

For each individual equity asset `i`, define:

```
mu_i = IC * sigma_i * z_i
```

where:

- `z_i = beta_v * v_i + beta_q * q_i + beta_b * b_i + beta_d * d_i` is the dimensionless composite fundamental score
- `sigma_i = sqrt(D_ii)` is the asset-specific residual risk from the factor model (annualized decimal)
- `IC` is the information coefficient, initially assumed at `0.04`
- `mu_i` is expected annualized excess return in decimal units

For ETF assets: `mu_ETF = 0`. They contribute no alpha.

After IC scaling, apply uncertainty and liquidity adjustments:

```
mu_tilde_i = mu_i - gamma_u * u_i - gamma_l * l_i
```

This should come from the alpha model only, and `mu_i` must be dimensionally consistent with the covariance matrix units before entering the optimizer.

## 2. Risk Model

Define:

- factor exposure matrix `B` in `R^(N x K)` (after hierarchical orthogonalization)
- factor covariance matrix `F` in `R^(K x K)` (estimated via 252-day EWMA, Ledoit-Wolf shrinkage)
- specific risk matrix `D` in `R^(N x N)` diagonal (estimated via 252-day EWMA residual variances)

Then portfolio covariance is:

```
Sigma = B F B' + D
```

This is the standard form the repo should move toward.

ETF assets are included in `B`, `F`, and `D` for risk estimation. They carry `mu = 0` in the alpha vector but their covariance terms inform the portfolio risk model.

## 3. Optimizer

Define weights `w`.

Base objective (minimization form):

```
minimize  -mu_tilde' w + lambda_r * w' Sigma w + lambda_h * ||w - w_ref||^2
```

subject to:

- `sum(w) = 1`
- `w_i >= 0` if long-only
- issuer, sector, country, currency, and liquidity constraints
- ETF sleeve floor constraints: `w_ETF_i >= floor_ETF_i(macro_state)`

`lambda_r = 3.0` is valid and theoretically grounded after IC scaling makes `mu_tilde` dimensionally consistent.

This is mathematically clear and market-standard.

## 4. Tail-Risk Overlay

Evaluate using loss convention:

```
CVaR_alpha(w)  <= L_cvar
CDaR_alpha(w)  <= L_cdar
```

If risk exceeds policy limits:

- tighten constraints
- increase ballast sleeves
- reject the allocation

---

## Exact Optimization Specification

This section defines the production optimizer in exact mathematical terms.

## 1. Sets And Indices

Let:

- `i = 1, ..., N` index assets
- `k = 1, ..., K` index risk factors
- `c = 1, ..., C` index countries
- `u = 1, ..., U` index currencies
- `s = 1, ..., S` index sectors
- `g = 1, ..., G` index sleeves

Examples of sleeves:

- `global_equity`
- `safe_haven_bond`
- `cash`
- `gold_commodity`
- `equity_index` (for ETF index exposure)

## 2. Decision Variables

Primary decision variable:

- `w_i`: final portfolio weight in asset `i`

Auxiliary variables for linearized concentration control:

- `z_i >= 0`: position size slack if a convex concentration penalty is added later

For phase 1 implementation, only `w_i` is strictly necessary.

## 3. Alpha Model Output

For each individual equity asset `i`, define:

```
z_i = beta_v * v_i + beta_q * q_i + beta_b * b_i + beta_d * d_i
```

where each component is cross-sectionally normalized at the rebalance date.

Recommended first weights:

- `beta_v = 0.35`
- `beta_q = 0.25`
- `beta_b = 0.25`
- `beta_d = 0.15`

Then convert to return units via IC scaling:

```
mu_i = IC * sigma_i * z_i        (for individual equity assets)
mu_i = 0                          (for ETF shelter assets)
```

where `IC = 0.04` initially and `sigma_i = sqrt(D_ii)` from the risk model.

This conversion ensures `mu_tilde' w` and `w' Sigma w` are in the same units and `lambda_r` has its standard CARA interpretation.

## 4. Risk Model

Let:

- `B in R^(N x K)` be the **orthogonalized** factor exposure matrix
- `F in R^(K x K)` be factor covariance (252-day EWMA, halflife 63 days, Ledoit-Wolf shrinkage)
- `D in R^(N x N)` be diagonal specific risk (252-day EWMA residual variance, numerical floor applied)

Then:

```
Sigma = B F B' + D
```

### Factor exposure design and orthogonalization

`B` is constructed using one-hot indicators for:

- sleeve (priority 1)
- country (priority 2)
- sector (priority 3)
- currency (priority 4)

After construction, apply hierarchical Gram-Schmidt orthogonalization in the order above. Lower-priority factor columns are projected to be orthogonal to all higher-priority columns. The resulting `B_ortho` replaces `B` in all downstream computations.

Optional later additions to `B`:

- style factors
- duration sensitivity
- commodity beta

### Covariance estimation specification

| Component | Window | Weighting | Shrinkage |
|---|---|---|---|
| Factor covariance `F` | 252 days | EWMA, halflife 63d | Ledoit-Wolf analytical |
| Specific risk `D_ii` | 252 days | EWMA, halflife 63d | Minimum floor: `1e-4` |

Ledoit-Wolf is applied to the exponentially weighted sample covariance matrix, not the raw sample covariance:

```python
# Pseudocode
S_ewm = returns.ewm(halflife=63).cov().iloc[-N:, :]  # last N x N block
alpha_lw, _ = ledoit_wolf(returns.values)             # shrinkage intensity
mu_target = np.trace(S_ewm) / N * np.eye(N)
F_estimated = (1 - alpha_lw) * S_ewm + alpha_lw * mu_target
```

### Specific risk

`D` is diagonal with entries:

```
D_ii = max(sigma_spec_i^2, 1e-4)
```

estimated from residual return variance after projecting asset returns onto the orthogonalized factor set `B_ortho`.

## 5. Uncertainty And Implementation Penalties

Define:

- `u_i`: uncertainty penalty from data quality, options-implied event risk, or missingness
- `l_i`: liquidity penalty coefficient

All three quantities (`mu_i`, `u_i`, `l_i`) must be on the same annualized return scale before combining.

Then define net expected return:

```
mu_tilde_i = mu_i - gamma_u * u_i - gamma_l * l_i
```

Vector form:

```
mu_tilde = mu - gamma_u * u - gamma_l * l
```

This keeps options and data quality in the risk-adjustment layer, not alpha.

## 6. Core Optimization Objective

The production objective:

```
minimize over w:

  L(w) = -mu_tilde' w + lambda_r * w' Sigma w + lambda_h * ||w - w_ref||^2
```

where:

- `lambda_r > 0` is the CARA risk-aversion coefficient (valid at `3.0` after IC scaling)
- `lambda_h >= 0` is the holdings-stability regularizer
- `w_ref` is the reference portfolio (current holdings if live; neutral sleeve-weighted if first run)

Interpretation:

- first term rewards structural expected return (in return units after IC scaling)
- second term penalizes total portfolio variance (in matching return-variance units)
- third term prevents unstable corner solutions

## 7. Equivalent Maximization Form

```
maximize over w:

  J(w) = mu_tilde' w - lambda_r * w' Sigma w - lambda_h * ||w - w_ref||^2
```

Both forms are equivalent; choose based on solver convention.

## 8. Hard Constraints

### 8.1 Full investment

```
sum_i w_i = 1
```

### 8.2 Long-only

```
w_i >= 0  for all i
```

### 8.3 Single-name cap

For each asset `i`:

```
w_i <= w_i^max
```

where `w_i^max = min(global_cap, liquidity_cap, uncertainty_cap, instrument_cap)`.

### 8.4 Sector caps

Let `A_sector` be the sector membership matrix.

For each sector `s`:

```
(A_sector' w)_s <= W_sector_s^max
```

### 8.5 Country caps

Let `A_country` be the country membership matrix.

For each country `c`:

```
(A_country' w)_c <= W_country_c^max
```

### 8.6 Currency exposure bands

Let `A_ccy` map assets to currency buckets.

For each currency `u`:

```
W_ccy_u^min <= (A_ccy' w)_u <= W_ccy_u^max
```

This replaces the old KR/US ticker split.

### 8.7 Sleeve constraints

Let `A_sleeve` map assets to sleeves.

For each sleeve `g`:

```
W_sleeve_g^min(macro_state) <= (A_sleeve' w)_g <= W_sleeve_g^max
```

The lower bound `W_sleeve_g^min` is a function of macro state for ETF shelter sleeves. In normal conditions it equals the base policy floor. Under stress it is tightened upward by the macro risk governor.

### 8.8 Liquidity constraints

For each asset `i`:

```
w_i <= kappa * ADV_i / NAV
```

where:

- `ADV_i` is average daily traded value (252-day)
- `NAV` is portfolio capital
- `kappa` is allowed participation rate

This should remain a hard implementation constraint.

## 9. Optional Tail-Risk Constraint

**Sign convention: loss convention throughout (positive = worse, consistent with Riskfolio-Lib).**

If a scenario return matrix `R_scn` is built, define portfolio scenario returns:

```
r_p = R_scn w
```

Then impose either:

```
CVaR_alpha(w) <= L_cvar          # expected tail loss does not exceed L_cvar
```

or:

```
CDaR_alpha(w) <= L_cdar          # conditional drawdown does not exceed L_cdar
```

Do **not** write `CVaR_alpha(r_p) >= -L_cvar`. That is the return convention and is inconsistent with Riskfolio-Lib.

Recommended policy:

- keep the main optimizer quadratic (Section 6)
- use `CVaR` or `CDaR` as a second-stage feasibility check or veto

This is more stable operationally than making `CDaR` the first-stage objective.

## 10. Stress-Conditioned Constraints

Let `m` denote macro stress state.

Instead of injecting macro alpha, change constraints conditionally.

If FX stress is active:

```
decrease W_KRW^max
increase W_USD^min
```

If equity stress is active:

```
increase W_sleeve_bond^min
increase W_sleeve_cash^min
reduce W_sleeve_equity^max
```

These adjustments are returned by `signals/macro.py` as constraint multipliers and passed to `portfolio/constraints.py`. No per-asset expected return vector is produced by the macro module.

## 11. Optional Black-Litterman Extension

If Black-Litterman is retained later, do it only after the alpha model is formalized.

Let:

- `pi` be prior expected return
- `Q` be view vector from structural alpha model (in return units after IC scaling)
- `P` be picking matrix
- `Omega` be view covariance (tied to `IC` uncertainty and data quality score)

Then the BL posterior can be used to replace `mu_tilde`:

```
mu_tilde := mu_BL - gamma_u * u - gamma_l * l
```

But BL should remain optional.
The base production system does not need it.

## 12. Recommended Default Hyperparameters

Initial defaults for implementation:

- `IC = 0.04`                             (assumed; update as snapshots accumulate)
- `EWMA_HALFLIFE = 63`                    (days; one quarter)
- `COVARIANCE_WINDOW = 252`               (days)
- `lambda_r = 3.0`                        (CARA risk aversion; valid after IC scaling)
- `lambda_h = 0.25`
- `gamma_u = 0.50`
- `gamma_l = 0.25`
- max single name: `0.10`
- max sector: `0.25`
- max country: `0.60`
- KRW band: `0.30` to `0.70`
- USD band: `0.30` to `0.70`
- cash sleeve min: `0.05`
- bond + cash sleeve min under stress: `0.15`

These are starting values, not permanent truths.

---

## Implementation Blueprint By File And Module

This section maps the mathematical design into concrete repo changes.

## Phase 0. Preserve Existing Files For Reference

Keep these files temporarily for comparison and fallback:

- `optimization/hrp.py`
- `optimization/black_litterman.py`
- `signals/trend.py`

They should remain importable during migration, but they must leave the main production path.

## Phase 1. Configuration Layer

### File: `config.py`

Replace current trend-centric and BL-centric top-level controls with grouped configuration blocks.

Add:

- `ALPHA_WEIGHTS`
- `RISK_MODEL_CONFIG`
- `OPTIMIZER_CONFIG`
- `CONSTRAINT_CONFIG`
- `STRESS_CONFIG`
- `SLEEVE_CONFIG`
- `ETF_SHELTER_CONFIG`

Exact keys to add:

```python
ALPHA_WEIGHTS = {
    "valuation": 0.35,
    "quality": 0.25,
    "balance_sheet": 0.25,
    "capital_discipline": 0.15
}

IC_INITIAL = 0.04                    # assumed information coefficient

COVARIANCE_WINDOW     = 252          # days
EWMA_HALFLIFE         = 63           # days (one quarter)
LEDOIT_WOLF_SHRINKAGE = True         # apply LW analytical shrinkage

OPTIMIZER_RISK_AVERSION  = 3.0       # lambda_r (valid after IC scaling)
OPTIMIZER_HOLDING_REG    = 0.25      # lambda_h
UNCERTAINTY_PENALTY      = 0.50      # gamma_u
LIQUIDITY_PENALTY        = 0.25      # gamma_l

MAX_WEIGHT_SINGLE        = 0.10
MAX_WEIGHT_SECTOR        = 0.25
MAX_WEIGHT_COUNTRY       = 0.60

MIN_WEIGHT_USD           = 0.30
MAX_WEIGHT_USD           = 0.70
MIN_WEIGHT_KRW           = 0.30
MAX_WEIGHT_KRW           = 0.70

MIN_WEIGHT_CASH          = 0.05
MIN_WEIGHT_BOND_CASH_STRESS = 0.15

MAX_PARTICIPATION_RATE   = 0.10

ETF_SHELTER_TICKERS = [
    "TLT", "IEF", "SGOV", "GLD", "DBC",
    "114260.KS", "148070.KS", "456880.KS",
    "069500.KS", "139260.KS"
]
```

De-emphasize or remove from main path:

- moving average settings
- envelope settings
- FF alpha weights
- hard tactical `+2/-2` defensive logic
- `VIX_CONFIDENCE_BASE` (replace with stress-regime bands)

## Phase 2. Universe And Metadata Layer

### File: `data/universe.py`

Current responsibility:

- raw ticker list generation

New responsibility:

- return a metadata-rich universe DataFrame with ETF vs equity classification

Required outputs per asset:

- `ticker`
- `country`
- `trading_currency`
- `instrument_type`          (`equity`, `etf_bond`, `etf_commodity`, `etf_cash`, `etf_index`)
- `sector`
- `sleeve`
- `is_etf_shelter`           (`True` for all ETF shelter assets; `False` for individual equities)
- `is_defensive`
- `is_safe_haven`

Required new functions:

- `get_universe_metadata()`
- `classify_instrument_type(ticker)`
- `assign_sleeve(metadata_row)`
- `is_etf_shelter(ticker)` -> `bool`

Output contract:

- one row per asset
- deterministic schema used by risk and optimization layers
- ETF shelter flag used by Phase 4 to exclude assets from fundamental alpha

## Phase 3. Market Data And Candidate Layer

### File: `data/loader.py`

Keep:

- price loading
- volume loading
- FX conversion utility if needed for reporting

Remove from primary selection logic:

- `ma_200` trend filter
- hard KR/US split

Replace `filter_candidates(...)` with:

- `build_candidate_frame(price_df, volume_df, metadata_df)`

This function should output:

- liquidity metrics
- market-cap proxy or market-cap field
- eligibility flags
- currency exposure tags
- `is_etf_shelter` flag (passed through from metadata)

Add:

- `compute_adv(volume_df, price_df, window)`
- `compute_liquidity_caps(candidate_df, nav)`
- `apply_basic_eligibility(candidate_df)`

Primary contract:

- candidates are selected globally
- no country quota is enforced at prefilter stage
- ETF shelter assets pass eligibility automatically (they are mandatory shelter, not alpha candidates)

## Phase 4. Fundamental Alpha Layer

### File: `signals/fundamental.py`

This becomes the production alpha module for **individual equity securities only**.

**ETF shelter assets must be excluded from this module.** Before computing any fundamental score, filter out assets where `metadata['is_etf_shelter'] == True`. ETF assets receive `mu_i = 0` in the alpha vector; they are not scored.

Split into explicit subfunctions:

- `fetch_fundamental_snapshot(ticker)`
- `build_fundamental_snapshot_table(tickers)`         (equity tickers only)
- `compute_valuation_features(snapshot_df)`
- `compute_quality_features(snapshot_df)`
- `compute_balance_sheet_features(snapshot_df)`
- `compute_capital_discipline_features(snapshot_df)`
- `normalize_alpha_features(feature_df)`              (cross-sectional Z-score normalization)
- `build_composite_score(feature_df, alpha_weights)`  -> `z_i` (dimensionless)
- `scale_to_expected_return(z, sigma_spec, ic)`       -> `mu_i` (annualized decimal return)
- `build_expected_return_vector(feature_df, sigma_spec_series, alpha_weights, ic)` -> full `mu` vector

Exact output tables:

1. raw snapshot table (equity assets only)
2. feature table
3. normalized feature table
4. composite score vector `z` (dimensionless)
5. expected return vector `mu` (annualized decimal, after IC scaling)

Missing-data policy:

- do not assign arbitrary neutral scores
- track missingness explicitly
- generate `data_quality_score` per asset (feeds `u_i` uncertainty penalty)

## Phase 5. Macro Risk Governor

### File: `signals/macro.py`

Rewrite from alpha producer into constraint modifier.

Required new functions:

- `get_macro_state()` -> `dict` with keys: `vix_level`, `fx_vol`, `stress_regime`
- `build_constraint_multipliers(macro_state)` -> `dict` of sleeve and currency adjustments
- `apply_macro_constraint_adjustments(base_constraints, multipliers)` -> adjusted constraints

Output contract:

- no direct per-asset expected return vector
- only portfolio-level constraint adjustments (sleeve floors, currency bands)

Stress regime classification:

```
Normal:   VIX < 20
Elevated: 20 <= VIX < 30  -> bond/cash floor +0.05
Stress:   VIX >= 30       -> bond/cash floor +0.10, equity cap reduced
FX:       fx_vol >= 0.05  -> KRW cap reduced, USD floor increased
```

## Phase 6. Options Uncertainty Layer

### File: `signals/options_skew.py`

Rewrite from directional skew alpha into uncertainty scoring.

Required new functions:

- `fetch_options_risk_snapshot(ticker)`
- `compute_event_risk_score(options_snapshot)`
- `build_uncertainty_penalty_vector(tickers)`

Output contract:

- `u_i` uncertainty penalty per asset (in annualized return units to match `mu_i` scale)
- optional cap multipliers for position sizing

No directional buy/sell views.

## Phase 7. Factor Risk Model

### File: `portfolio/factor_loading.py`

This file should be repurposed, not removed.

Current role:

- FF regression and residual alpha

New role:

- factor exposure construction with orthogonalization
- factor covariance estimation (EWMA + Ledoit-Wolf)
- specific risk estimation (EWMA)

Required new functions:

- `build_factor_exposure_matrix(metadata_df, candidate_df)` -> raw `B`
- `orthogonalize_factor_exposures(B, priority_order)` -> `B_ortho`
- `estimate_factor_returns(asset_return_df, B_ortho)` -> factor return series
- `estimate_factor_covariance(factor_return_df, window=252, halflife=63)` -> `F` with LW shrinkage
- `estimate_specific_risk(asset_return_df, B_ortho, factor_return_df, window=252, halflife=63)` -> diagonal `D`
- `build_total_covariance(B_ortho, F, D)` -> `Sigma`

Orthogonalization priority order (fixed):

```python
FACTOR_PRIORITY = ["sleeve", "country", "sector", "currency"]
```

Covariance estimation specification (mandatory):

| Parameter | Value |
|---|---|
| Window | 252 trading days |
| Weighting | EWMA, `halflife=63` days |
| Factor covariance shrinkage | Ledoit-Wolf analytical |
| Specific risk floor | `max(D_ii, 1e-4)` |

Phase-1 factor set:

- sleeve (priority 1)
- country (priority 2)
- sector (priority 3)
- currency (priority 4)

Later factor additions:

- style
- duration
- commodity sensitivity

Note: ETF shelter assets are included in the factor risk model. Their factor exposures inform portfolio-level risk estimates even though their alpha is zero.

## Phase 8. Primary Optimizer

### File: `optimization/mean_risk.py`

Create this new file.

This becomes the main production optimizer.

Required functions:

- `build_reference_portfolio(current_holdings, sleeve_config)` -> `w_ref`
- `build_constraint_matrices(metadata_df, macro_constraints, nav, config)` -> constraint object
- `solve_constrained_mean_risk(mu_tilde, sigma, constraints, w_ref, lambda_r, lambda_h)` -> `w`
- `postprocess_weights(raw_weights, min_weight_floor=0.01)` -> cleaned `w`

Objective to implement exactly (using `cvxpy`):

```python
import cvxpy as cp

w = cp.Variable(N)
objective = cp.Minimize(
    -mu_tilde @ w
    + lambda_r * cp.quad_form(w, Sigma)
    + lambda_h * cp.sum_squares(w - w_ref)
)
constraints = [
    cp.sum(w) == 1,
    w >= 0,
    # sector caps: A_sector @ w <= sector_caps
    # country caps: A_country @ w <= country_caps
    # currency bands: ccy_min <= A_ccy @ w <= ccy_max
    # sleeve bounds: sleeve_min(macro) <= A_sleeve @ w <= sleeve_max
    # liquidity caps: w <= liquidity_cap_vec
]
problem = cp.Problem(objective, constraints)
problem.solve(solver=cp.CLARABEL)
```

This file becomes the optimizer imported by `main.py`.

The two-stage shelter/alpha design is expressed through sleeve constraints (ETF floor bounds) rather than separate optimizer calls. The single QP handles both simultaneously.

## Phase 9. Legacy Optimizer Retention

### File: `optimization/hrp.py`

Keep, but change role in documentation to:

- benchmark allocator
- fallback allocator

### File: `optimization/black_litterman.py`

Keep, but change role to:

- optional posterior-return engine

not mandatory in main production path.

## Phase 10. Constraints Layer

### File: `portfolio/constraints.py`

Expand into a formal constraints builder.

Required functions:

- `build_weight_caps(candidate_df, nav, config)` -> per-asset cap vector
- `build_country_constraints(metadata_df, config)` -> `(A_country, country_cap_vec)`
- `build_sector_constraints(metadata_df, config)` -> `(A_sector, sector_cap_vec)`
- `build_currency_constraints(metadata_df, config)` -> `(A_ccy, ccy_min, ccy_max)`
- `build_sleeve_constraints(metadata_df, macro_multipliers, config)` -> `(A_sleeve, sleeve_min, sleeve_max)`
- `merge_constraint_sets(...)` -> unified constraint object for `optimization/mean_risk.py`

The sleeve constraint builder must accept `macro_multipliers` from `signals/macro.py` to apply stress-conditioned floor tightening.

This file outputs a structured constraint object consumed by `optimization/mean_risk.py`.

## Phase 11. Portfolio Reporting Layer

### File: `portfolio/selector.py`

Current role:

- top-N selection after optimizer

New role:

- portfolio validation
- exposure report generation
- export formatting

Required functions:

- `validate_portfolio(weights, constraints)` -> `bool` + violation report
- `build_exposure_report(weights, metadata_df)` -> country, sector, currency, sleeve breakdown
- `build_risk_report(weights, sigma, B_ortho, F, D)` -> factor risk contribution
- `build_alpha_report(weights, mu, mu_tilde)` -> attribution of expected return
- `export_portfolio_bundle(weights, exposure_report, risk_report, alpha_report, output_dir)`

This file should no longer decide the portfolio by ranking top weights.
The optimizer output is the portfolio.

## Phase 12. Execution Layer

### File: `portfolio/execution.py`

Keep as execution-only.

Remove conceptual dependence on alpha or risk logic.

Required updates:

- consume final optimized weights
- check tradability vs liquidity caps
- generate executable order plan

Optional future functions:

- `estimate_trade_notional(weights, nav)`
- `estimate_participation_rate(order_df, adv_df)`

## Phase 13. Main Orchestration

### File: `main.py`

Replace current pipeline with new pipeline:

```
1.  build universe metadata                      (data/universe.py)
2.  load price and volume data                   (data/loader.py)
3.  build candidate frame with ETF shelter flags (data/loader.py)
4.  estimate factor risk model                   (portfolio/factor_loading.py)
      -> orthogonalize B
      -> estimate F (EWMA 252d, halflife 63d, Ledoit-Wolf)
      -> estimate D (EWMA 252d, halflife 63d)
      -> compute Sigma = B_ortho F B_ortho' + D
      -> extract sigma_spec_i = sqrt(D_ii)
5.  fetch fundamental snapshot (equity assets only)  (signals/fundamental.py)
6.  compute normalized fundamental scores z_i        (signals/fundamental.py)
7.  build expected return vector via IC scaling       (signals/fundamental.py)
      -> mu_i = IC * sigma_i * z_i  (equity assets)
      -> mu_i = 0                    (ETF shelter assets)
8.  compute uncertainty penalties u_i            (signals/options_skew.py)
9.  apply adjustments: mu_tilde = mu - gamma_u*u - gamma_l*l
10. get macro state and constraint adjustments   (signals/macro.py)
11. build constraint set with macro adjustments  (portfolio/constraints.py)
12. solve constrained mean-risk optimizer        (optimization/mean_risk.py)
13. run tail-risk and stress checks (loss conv.) (evaluation/metrics.py)
      -> if CDaR_alpha(w) > L_cdar: tighten and re-solve or veto
14. validate portfolio and build reports         (portfolio/selector.py)
15. generate execution plan                      (portfolio/execution.py)
16. export weights, exposures, reports, snapshots
```

Recommended orchestration functions:

- `build_live_structural_portfolio()` -> unified weight vector
- `run_stress_gate(weights, scenario_bundle)` -> pass/fail + adjusted constraints
- `export_live_decision_bundle(weights, reports, snapshot_dir)`

## Phase 14. Backtest Separation

### File: `backtest/engine.py`

Keep, but redefine scope.

Short-term role:

- replay market-risk mechanics
- replay optimization mechanics using historically estimated risk (EWMA + LW from historical window)

Not yet valid for:

- full structural alpha replay (requires historical fundamental snapshots)

Required new separation:

- `run_historical_risk_replay(...)` -> replayable using price/volume history only
- `run_snapshot_based_walk_forward(...)` -> only activate after snapshot storage is built

## Phase 15. Evaluation Layer

### File: `evaluation/metrics.py`

Keep, but expand.

All tail-risk metrics must use the loss convention:

```
CVaR_alpha(w) reported as positive loss fraction
CDaR_alpha(w) reported as positive drawdown fraction
```

Add:

- factor contribution to risk (using `B_ortho`, `F`, `D` decomposition)
- country exposure summary
- currency exposure summary
- shelter sleeve allocation summary (ETF vs equity split)
- scenario loss table
- ballast sleeve share

## Phase 16. Output And Snapshot Storage

### New directory: `outputs/snapshots/`

Store per decision date:

- universe metadata snapshot
- candidate table (with ETF shelter flags)
- fundamental snapshot table (equity assets only)
- alpha feature table
- composite score vector `z`
- IC assumption used
- expected return vector `mu` (post IC scaling)
- uncertainty vector `u`
- factor exposure matrix `B_ortho`
- factor covariance `F` (post shrinkage)
- specific risk `D`
- macro state and constraint multipliers
- final constraint set
- final weights
- tail-risk metrics (loss convention)

This is required for auditability and future point-in-time validation.

---

## Currency Risk Design

This must replace the current hard KR/US split.

### Current flaw

The repo currently approximates FX control through country count.

That is not acceptable.

### New design

Treat currency as a first-class portfolio exposure.

For each asset:

- assign funding / reporting / trading currency
- assign KRW-linked or USD-linked exposure bucket

Then constrain portfolio exposure directly.

### Example constraints

```
W_USD^min <= (A_ccy' w)_USD <= W_USD^max
W_KRW^min <= (A_ccy' w)_KRW <= W_KRW^max
```

Under FX stress (fx_vol >= 0.05):

```
W_KRW^max is reduced
W_USD^min is increased
```

These are passed through `signals/macro.py` -> `portfolio/constraints.py` as constraint tightening adjustments.

### Result

The country mix becomes endogenous:

- determined by alpha and constraints

rather than forced by arbitrary quotas.

---

## Treatment Of Safe-Haven Assets

Current repo logic forces defensive ETFs through view overrides.

That is replaced by the ETF Shelter Architecture (Section F of Recommended Institutional Architecture).

### New rule

Safe-haven assets are ETF shelter instruments.

They are controlled by sleeve floor constraints, not alpha scores:

- `bond` sleeve minimum (TLT, IEF, KODEX 국고채 ETFs)
- `cash` sleeve minimum (SGOV, ACE SOFR ETF)
- `safe_haven_commodity` sleeve minimum (GLD)

These floors are:

- set at base policy minimums in normal conditions
- tightened upward by the macro risk governor under stress

This is institutionally cleaner than assigning ad hoc alpha boosts.

---

## Treatment Of Options Data

Options should no longer be used as directional "smart money" alpha.

### Recommended role

Use options-implied information only as:

- uncertainty penalty `u_i` (in annualized return units, matching `mu_i` scale)
- event-risk modifier
- position-cap reducer

That keeps its information content while avoiding weak causal claims.

---

## Backtesting Policy

The redesigned repo must be honest about what is and is not historically validated.

## Immediate rule

Only the risk and execution mechanics are replayable with current repo data.

The live fundamental alpha engine is not yet point-in-time validated because the repo does not store historical snapshots of:

- fundamentals
- analyst fields
- option surfaces
- macro states used in decisions

## Therefore the repo should operate in two modes

### Mode 1. Live Portfolio Construction

Uses:

- current fundamental alpha (equity assets only, IC-scaled)
- estimated risk model (EWMA 252d, halflife 63d, Ledoit-Wolf)
- live macro-conditioned constraints and ETF shelter floors

### Mode 2. Historical Replay

Uses:

- historical market data
- historical risk estimation (EWMA 252d, halflife 63d, Ledoit-Wolf applied to rolling windows)
- only snapshot-available alpha inputs

Until snapshot storage is built, the repo should not claim that the full alpha engine has been walk-forward validated. Historical replay validates risk mechanics only.

---

## Concrete Module Rewrite Plan

## 1. `config.py`

### Remove as first-class controls

- moving average settings
- envelope parameters
- trend weights
- FF alpha settings
- hard tactical view overrides

### Add

- `ALPHA_WEIGHTS`
- `IC_INITIAL = 0.04`
- `COVARIANCE_WINDOW = 252`
- `EWMA_HALFLIFE = 63`
- `LEDOIT_WOLF_SHRINKAGE = True`
- risk aversion parameter
- currency exposure bands
- country and sector caps
- sleeve definitions
- `ETF_SHELTER_TICKERS` list
- stress policy thresholds (regime bands)
- liquidity thresholds

## 2. `data/universe.py`

### Keep

- universe assembly

### Add

- instrument type classification (`equity` vs `etf_*`)
- `is_etf_shelter` flag
- country metadata
- trading currency metadata
- sleeve metadata
- sector mapping

## 3. `data/loader.py`

### Remove

- trend-based eligibility
- hard KR/US quota split

### Add

- current liquidity filters
- market-cap filters
- candidate metadata table with `is_etf_shelter` flag
- exposure tags for optimizer

ETF shelter assets pass eligibility filters automatically. They are not filtered by liquidity or trend criteria.

## 4. `signals/trend.py`

### Action

Remove from the main path.

Keep only if needed as a research-only legacy module.

## 5. `signals/fundamental.py`

### Action

Promote to primary alpha engine for equity assets.

### Rewrite goals

- output raw structural metrics for equity assets only
- output composite Z-score `z_i` (dimensionless, cross-sectionally normalized)
- output expected return `mu_i` after IC scaling (annualized decimal)
- separate missing-data handling from economic scoring
- avoid arbitrary default scores

## 6. `signals/macro.py`

### Action

Convert to constraint-governor module.

### New role

- classify macro stress regime
- return constraint multipliers (sleeve floor adjustments, currency band tightening)
- not generate direct expected returns

## 7. `signals/options_skew.py`

### Action

Convert to uncertainty-penalty module.

### New role

- `u_i` penalty in annualized return units (consistent scale with `mu_i`)
- cap multipliers
- event-risk modifiers

not directional alpha.

## 8. `portfolio/factor_loading.py`

### Action

Replace with formal factor-risk model utilities including orthogonalization and EWMA + LW covariance estimation.

### New role

- build factor exposure matrix `B`
- orthogonalize `B` by Gram-Schmidt hierarchy (sleeve > country > sector > currency)
- estimate factor covariance `F` (252-day EWMA, halflife 63d, Ledoit-Wolf)
- estimate specific risk `D` (252-day EWMA, halflife 63d, numerical floor)
- build total covariance `Sigma`

## 9. `optimization/hrp.py`

### Action

Keep as research or fallback allocator only.

### New role

- diversification benchmark
- fallback portfolio

not primary construction engine.

## 10. `optimization/black_litterman.py`

### Action

Refactor to optional module.

### New role

Used only if `BL` is enabled and the fundamental alpha model is formalized with clean priors and IC-consistent view uncertainty.

It should not remain mandatory in the main path.

## 11. `portfolio/constraints.py`

### Action

Expand heavily.

### New constraints

- issuer cap
- sector cap
- country cap
- currency band
- sleeve bounds (macro-conditioned for ETF shelter assets)
- liquidity cap
- optional event-risk caps

## 12. `portfolio/selector.py`

### Action

Replace top-N postprocessing with optimizer output postchecks and reporting.

### New role

- validation
- exposure summaries (country, sector, currency, sleeve, ETF vs equity)
- risk attribution (factor contribution using `B_ortho`, `F`, `D`)
- reporting

## 13. `optimization/`

### Add primary module

Create `optimization/mean_risk.py`:

- constrained mean-risk allocator using `cvxpy`
- objective: `minimize -mu_tilde' w + lambda_r * quad_form(w, Sigma) + lambda_h * sum_squares(w - w_ref)`
- constraints: full investment, long-only, issuer/sector/country/currency/sleeve/liquidity caps
- ETF shelter floors expressed as sleeve lower bounds

This file becomes the production engine.

## 14. `backtest/engine.py`

### Action

Separate:

- replayable risk mechanics (EWMA + LW on historical windows)
- live-only alpha logic

### New role

- `run_historical_risk_replay`: uses historical price data, EWMA + LW covariance, no fundamental alpha
- `run_snapshot_based_walk_forward`: requires snapshot storage (future capability)

## 15. `evaluation/metrics.py`

### Action

Keep, but expand.

### Convention fix

All tail-risk metrics must use the loss convention (positive = worse). Update any code using `CVaR_alpha(r_p) >= -L` to `CVaR_alpha(w) <= L`.

### Add

- factor contribution to risk
- country exposure summary
- currency exposure summary
- shelter sleeve share vs alpha sleeve share
- scenario loss table
- ballast sleeve report

---

## Minimum Viable Institutional Redesign

If the repo is updated in the smallest coherent way, do this in order:

1. remove trend alpha from the main path
2. remove KR/US hard candidate split
3. classify ETF shelter assets and exclude them from fundamental alpha scoring
4. replace FF residual alpha with structural fundamental expected return (equity assets only)
5. apply IC scaling: `mu_i = IC * sigma_i * z_i` before optimizer
6. build factor exposure matrix `B`, orthogonalize by sleeve > country > sector > currency
7. estimate `F` and `D` using 252-day EWMA (halflife 63d) with Ledoit-Wolf shrinkage
8. optimize with `cvxpy` mean-risk QP including explicit country, sector, currency, sleeve, and liquidity constraints
9. set ETF sleeve floors as lower bounds in the optimizer (macro-conditioned)
10. keep `CDaR` / `CVaR` as a constraint (loss convention: `CDaR_alpha(w) <= L_cdar`)
11. keep `HRP` only as fallback or benchmark
12. make `BL` optional, not mandatory

This is the cleanest path from the current repo to a market-accepted architecture.

---

## What Should Not Be Done

- do not preserve trend signals as a small alpha component
- do not use option skew as directional alpha
- do not keep the hard KR/US split
- do not rely on defensive ETF score overrides
- do not treat `HRP` as the only mathematically serious path
- do not claim full walk-forward validation without snapshot storage
- do not score ETF shelter assets with equity fundamental factors
- do not mix alpha score units with covariance units in the optimizer without IC scaling
- do not apply factor covariance estimation without prior orthogonalization of `B`
- do not use the return convention for CVaR/CDaR anywhere in code that interfaces with Riskfolio-Lib

---

## Acceptance Criteria

The redesign is successful only if all of the following become true:

1. alpha comes from structural fundamentals, not past price trends
2. alpha scores are converted to annualized return units via IC scaling before entering the optimizer
3. factor exposures in `B` are orthogonalized before estimating `F` and `D`
4. CVaR and CDaR are expressed in the loss convention uniformly throughout the codebase
5. risk is modeled separately through an explicit factor or covariance framework with 252-day EWMA and Ledoit-Wolf shrinkage
6. currency risk is handled directly through exposure constraints
7. ETF shelter assets receive zero fundamental alpha and are allocated through policy sleeve floor constraints
8. safe-haven assets are controlled by macro-conditioned sleeve rules, not ad hoc score overrides
9. `CDaR` remains part of resilience control but is no longer the sole core allocator
10. `HRP` is demoted to benchmark or fallback status
11. `BL` is only used if priors, views, and uncertainties are made internally coherent and IC-consistent
12. documentation clearly distinguishes live construction from historical validation

---

## Final Recommendation

The repo should move from:

- `trend + mixed views + HRP prior + BL optimizer + CDaR emphasis`

to:

- `IC-scaled fundamental alpha (equity only) + orthogonalized factor risk model (EWMA 252d LW) + constrained QP optimizer + ETF shelter sleeve floors + CDaR/stress overlay (loss convention)`

That is the best way to satisfy all three goals at once:

- preserve the resilience-first idea
- stay mathematically clear and dimensionally consistent
- align with methods widely accepted in real portfolio construction
