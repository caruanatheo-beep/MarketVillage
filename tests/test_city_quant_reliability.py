"""Noé must never publish non-finite backtest results."""

import json

import pandas as pd
import pytest

from internships_project import city_services, city_specialists
from internships_project.marketdesk_city import CityError
from src import data


def history(values):
    return pd.Series(values, index=pd.date_range("2025-01-01", periods=len(values)), dtype=float)


@pytest.mark.parametrize("offset", [10, 100, 159])
@pytest.mark.parametrize("invalid", [float("inf"), float("-inf")])
def test_nonfinite_closes_are_rejected_even_outside_trading_window(offset, invalid):
    prices = history([100 + i for i in range(160)])
    prices.iloc[offset] = invalid

    with pytest.raises(CityError, match="clôtures.*finies"):
        city_specialists.backtest(prices, lookback=20)


def test_finite_closes_with_overflowing_returns_are_rejected():
    prices = history([1e-100] * 159 + [1e308])

    with pytest.raises(CityError, match="non finis"):
        city_specialists.backtest(prices, lookback=20, strategy="mean_reversion")


def test_finite_returns_with_overflowing_equity_are_rejected():
    prices = history([1e-100, 1e100] * 80)

    with pytest.raises(CityError, match="non finis"):
        city_specialists.backtest(prices, lookback=5, strategy="mean_reversion")


def test_finite_equity_with_overflowing_volatility_is_rejected():
    prices = history([100 + i for i in range(159)] + [1e165])

    with pytest.raises(CityError, match="non finis"):
        city_specialists.backtest(prices, lookback=20)


@pytest.mark.parametrize("invalid", [False, True])
def test_noe_agent_rejects_invalid_history_and_delivers_serializable_valid_report(monkeypatch, invalid):
    prices = history([100.0] * 200)
    if invalid:
        prices.iloc[100] = float("inf")

    def fetch_history(self, ids, days):
        return pd.DataFrame({"Date": prices.index, "S&P 500": prices.values}), []

    monkeypatch.setattr(data.FredCollector, "fetch_history", fetch_history)
    parameters = {"operation": "quant_report"}
    if invalid:
        with pytest.raises(CityError, match="clôtures.*finies"):
            city_services.run_agent("finance_tutor", "test-user", parameters)
    else:
        report = city_services.run_agent("finance_tutor", "test-user", parameters)
        json.dumps(report, allow_nan=False)
        assert report["metrics"]["sharpe_rf_zero"] is None
        assert report["metrics"]["total_return"] == 0
        assert all(point["value"] == 1 for point in report["equity"])
