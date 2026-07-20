# -*- coding: utf-8 -*-
"""
backtest/engine.py
==================
Separated backtest engines:

  run_historical_risk_replay     : price-only, NO fundamental data required.
                                   Computes performance metrics from a static
                                   or rolling weight schedule.

  run_snapshot_based_walk_forward: requires SNAPSHOT_DIR snapshots of
                                   fundamental data saved at each rebalance date.
                                   Full pipeline re-run per month.

Design principles:
  - No look-ahead bias: data cut at current_date inclusive
  - Monthly rebalancing on last trading day of each month
  - vectorbt used for P&L simulation
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd
import vectorbt as vbt
from contextlib import redirect_stdout, redirect_stderr
from config import BACKTEST_SCENARIOS, BACKTEST_INITIAL_CAPITAL, BACKTEST_COMMISSION, SNAPSHOT_DIR

warnings.filterwarnings("ignore")


# ── utility ───────────────────────────────────────────────────────────────────

def _get_monthly_rebalance_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Returns the last trading day of each calendar month within index."""
    try:
        dates = index.to_series().resample("ME").last().dropna()
    except ValueError:
        dates = index.to_series().resample("M").last().dropna()
    return pd.DatetimeIndex(dates)


def _slice_scenario(prices: pd.DataFrame, scenario_name: str) -> pd.DataFrame:
    start, end = BACKTEST_SCENARIOS[scenario_name]
    subset = prices.loc[start:end] if end else prices.loc[start:]
    avail  = subset.columns[subset.iloc[0].notna()]
    return subset[avail]


def _run_vbt(prices: pd.DataFrame, weights_df: pd.DataFrame) -> object:
    """Executes a vectorbt simulation from a weights DataFrame (NaN = no trade)."""
    return vbt.Portfolio.from_orders(
        close       = prices,
        size        = weights_df,
        size_type   = "target_percent",
        init_cash   = BACKTEST_INITIAL_CAPITAL,
        fees        = BACKTEST_COMMISSION,
        freq        = "D",
        cash_sharing= True,
    )


# ── Engine 1: Historical risk replay (price-only) ─────────────────────────────

class HistoricalRiskReplay:
    """
    Simulates portfolio performance from a pre-computed weight schedule or
    a static weight vector.  No fundamental/alpha re-computation required.

    Use case:
      - Stress-test a known allocation across crisis windows
      - Benchmark comparison (HRP, 1/N, etc.)
    """

    def __init__(self, price_data: pd.DataFrame):
        self.prices = price_data

    def run_static(
        self,
        static_weights: pd.Series,
        scenario_name: str,
    ) -> object:
        """Buy-and-hold simulation. Warning: look-ahead bias if weights were fit on full history."""
        subset = _slice_scenario(self.prices, scenario_name)
        w = static_weights.reindex(subset.columns).fillna(0.0)
        total = w.sum()
        if total < 1e-8:
            return None
        w = w / total
        weights_df = pd.DataFrame(
            [w.values] * len(subset),
            index=subset.index,
            columns=subset.columns,
        )
        return _run_vbt(subset, weights_df)

    def run_rolling(
        self,
        weight_schedule: pd.DataFrame,
        scenario_name: str,
    ) -> object:
        """
        Simulates from a pre-computed weight_schedule DataFrame
        (index = rebalance dates, columns = tickers).
        Rebalances only on dates present in the schedule.
        """
        subset = _slice_scenario(self.prices, scenario_name)
        weights_df = pd.DataFrame(
            np.nan, index=subset.index, columns=subset.columns,
        )
        for date in weight_schedule.index:
            if date in subset.index:
                row = weight_schedule.loc[date].reindex(subset.columns).fillna(0.0)
                total = row.sum()
                if total > 1e-8:
                    weights_df.loc[date] = row / total
        return _run_vbt(subset, weights_df)

    def run_all_scenarios_static(self, static_weights: pd.Series) -> dict:
        return {name: self.run_static(static_weights, name) for name in BACKTEST_SCENARIOS}


# ── Engine 2: Snapshot-based walk-forward ────────────────────────────────────

class SnapshotWalkForward:
    """
    Full pipeline re-run each month using saved fundamental snapshots.
    Requires SNAPSHOT_DIR to contain pickled DataFrames named YYYY-MM-DD.pkl.

    Each snapshot file must contain the full metadata and fundamental table
    as of that date (no point-in-time look-through).
    """

    def __init__(
        self,
        price_data: pd.DataFrame,
        volume_data: pd.DataFrame,
        strategy_func: callable,
    ):
        self.prices   = price_data
        self.volumes  = volume_data
        self.strategy = strategy_func

    def _load_snapshot(self, date: pd.Timestamp) -> dict | None:
        """Loads the nearest available snapshot at or before date."""
        if not os.path.isdir(SNAPSHOT_DIR):
            return None
        available = sorted([
            f for f in os.listdir(SNAPSHOT_DIR) if f.endswith(".pkl")
        ])
        key = date.strftime("%Y-%m-%d")
        candidates = [f for f in available if f.replace(".pkl", "") <= key]
        if not candidates:
            return None
        fname = candidates[-1]
        try:
            return pd.read_pickle(os.path.join(SNAPSHOT_DIR, fname))
        except Exception:
            return None

    def run_scenario(self, scenario_name: str) -> object | None:
        """
        Walk-forward simulation for a single scenario window.
        Calls strategy_func(past_prices, past_volumes, snapshot) at each rebalance date.
        """
        subset = _slice_scenario(self.prices, scenario_name)
        vol_sub = self.volumes.reindex(index=subset.index, columns=subset.columns)

        if subset.empty:
            return None

        monthly_dates = _get_monthly_rebalance_dates(subset.index)
        weights_df    = pd.DataFrame(np.nan, index=subset.index, columns=subset.columns)

        for i, current_date in enumerate(monthly_dates):
            print(
                f"   [WF] {scenario_name} {current_date.strftime('%Y-%m')} "
                f"({i+1}/{len(monthly_dates)})", end="\r"
            )
            sys.stdout.flush()

            past_prices  = self.prices.loc[:current_date]
            past_volumes = self.volumes.loc[:current_date]
            snapshot     = self._load_snapshot(current_date)

            if len(past_prices) < 252:
                weights_df.loc[current_date] = 0.0
                continue

            try:
                with open(os.devnull, "w") as f, redirect_stdout(f), redirect_stderr(f):
                    w = self.strategy(past_prices, past_volumes, snapshot)
            except Exception as e:
                print(f"\n   [ERROR] {current_date.strftime('%Y-%m')}: {e}")
                weights_df.loc[current_date] = 0.0
                continue

            if w is None or w.sum() < 1e-8:
                weights_df.loc[current_date] = 0.0
                continue

            w_reindexed = w.reindex(subset.columns).fillna(0.0)
            weights_df.loc[current_date] = (w_reindexed / w_reindexed.sum()).values

        print(f"\n   [DONE] {scenario_name}")
        return _run_vbt(subset, weights_df)

    def run_all_scenarios(self) -> dict:
        return {name: self.run_scenario(name) for name in BACKTEST_SCENARIOS}


# ── Legacy compatibility ───────────────────────────────────────────────────────

class ResilientBacktester:
    """
    Backward-compatible wrapper that delegates to SnapshotWalkForward
    when strategy_func provided, else HistoricalRiskReplay static.
    """

    def __init__(self, price_data: pd.DataFrame, strategy_func: callable | None = None):
        self.prices   = price_data
        self.strategy = strategy_func

    def run_single_scenario(
        self,
        scenario_name: str,
        static_weights: pd.Series | None = None,
    ) -> object | None:
        if self.strategy is not None:
            engine = SnapshotWalkForward(
                self.prices,
                pd.DataFrame(),
                lambda p, v, s: self.strategy(p),
            )
            return engine.run_scenario(scenario_name)
        else:
            if static_weights is None:
                return None
            engine = HistoricalRiskReplay(self.prices)
            return engine.run_static(static_weights, scenario_name)

    def run_all_scenarios(self, static_weights: pd.Series | None = None) -> dict:
        return {
            name: self.run_single_scenario(name, static_weights)
            for name in BACKTEST_SCENARIOS
        }
