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


@pytest.mark.parametrize("strategy", ["momentum", "mean_reversion"])
@pytest.mark.parametrize("remaining", [0.5, 1.0])
def test_noe_does_not_publish_performance_after_costs_exhaust_capital(
        monkeypatch, strategy, remaining):
    # The last close loses 99% or 99.5%; the final 1% liquidation cost
    # exhausts the long/cash portfolio although all inputs remain finite.
    prices = history([100 + i if strategy == "momentum" else 300 - i
                      for i in range(160)])
    prices.iloc[-1] = prices.iloc[-2] * remaining / 100

    def fetch_history(self, ids, days):
        return pd.DataFrame({"Date": prices.index, "S&P 500": prices.values}), []

    monkeypatch.setattr(data.FredCollector, "fetch_history", fetch_history)

    with pytest.raises(CityError, match="capital.*épuisé"):
        city_services.run_agent("finance_tutor", "test-user", {
            "operation": "quant_report", "strategy": strategy, "cost_bps": 100})


def test_severe_loss_with_positive_capital_remains_reportable():
    prices = history([100 + i for i in range(160)])
    prices.iloc[-1] = prices.iloc[-2] * 0.02

    result = city_specialists.backtest(prices, cost_bps=100)

    assert -1 < result["metrics"]["total_return"] < -0.9
    assert -1 < result["metrics"]["max_drawdown"] < -0.9
    assert all(point["value"] > 0 for point in result["equity"])
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("final_factor", [1e-8, 1 + 1e-8])
def test_noe_published_capital_preserves_small_balances_and_moves(monkeypatch, final_factor):
    # Enter a long position after the warm-up, then apply one final movement.
    # Rounding to six decimals used to turn these into zero capital or no gain.
    prices = history([100.0 + i for i in range(160)])
    capital_before_move = prices.iloc[-2] / prices.iloc[60]
    prices.iloc[-1] = prices.iloc[-2]
    prices.iloc[-1] *= final_factor

    def fetch_history(self, ids, days):
        return pd.DataFrame({"Date": prices.index, "S&P 500": prices.values}), []

    monkeypatch.setattr(data.FredCollector, "fetch_history", fetch_history)

    report = city_services.run_agent("finance_tutor", "test-user", {
        "operation": "quant_report", "cost_bps": 0})
    published = json.loads(json.dumps(report, allow_nan=False))
    capital = published["equity"][-1]["value"]

    assert capital > 0
    assert capital != published["equity"][-2]["value"]
    assert capital == pytest.approx(capital_before_move * final_factor, rel=1e-8, abs=0)
    assert capital - 1 == published["metrics"]["total_return"]
    assert published["equity"][-2]["value"] == pytest.approx(capital_before_move)
    assert published["as_of"] == prices.index[-1].date().isoformat()


def test_underflowing_capital_does_not_publish_a_flat_zero_equity_curve():
    prices = history([10 ** (300 - i * 600 / 159) for i in range(160)])

    with pytest.raises(CityError, match="capital.*épuisé"):
        city_specialists.backtest(prices, strategy="mean_reversion", cost_bps=0)


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


@pytest.mark.parametrize("invalid_date", [None, "not a date", "2025-02-30", 42, "2099-01-01", "2999-01-01"])
def test_noe_agent_rejects_undated_or_future_history(monkeypatch, invalid_date):
    prices = history([100 + i for i in range(200)])
    dates = list(prices.index)
    dates[10] = invalid_date  # Even dates before the trading window must be valid.

    def fetch_history(self, ids, days):
        return pd.DataFrame({"Date": dates, "S&P 500": prices.values}), []

    monkeypatch.setattr(data.FredCollector, "fetch_history", fetch_history)

    with pytest.raises(CityError, match="dates.*passées ou présentes"):
        city_services.run_agent("finance_tutor", "test-user", {"operation": "quant_report"})


def test_noe_report_dates_follow_usable_chronological_closes(monkeypatch):
    prices = history([100 + i for i in range(200)])
    baseline = city_specialists.backtest(prices)
    # The provider can return unsorted dates and a final day without a close.
    rows = list(zip(prices.index.strftime("%Y-%m-%d"), prices.values))
    rows.append(("2025-07-20", None))
    frame = pd.DataFrame(rows[::-1], columns=["Date", "S&P 500"])
    monkeypatch.setattr(data.FredCollector, "fetch_history", lambda *args, **kwargs: (frame, []))

    report = city_services.run_agent("finance_tutor", "test-user", {"operation": "quant_report"})

    assert report["equity"] == baseline["equity"]
    assert report["metrics"] == baseline["metrics"]
    assert report["as_of"] == "2025-07-19"
    assert report["as_of"] == report["equity"][-1]["date"]


@pytest.mark.parametrize("last_date,eligible", [
    ("2025-07-21T00:30:00+02:00", True),
    ("2025-07-20T23:30:00-02:00", False),
])
def test_backtest_uses_utc_calendar_at_future_date_boundary(monkeypatch, last_date, eligible):
    class FixedDatetime(city_specialists.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2025, 7, 20, 12, tzinfo=city_specialists.timezone.utc)

    monkeypatch.setattr(city_specialists, "datetime", FixedDatetime)
    prices = history([100 + i for i in range(200)])
    dates = list(prices.index)
    dates[-1] = last_date
    prices.index = dates

    if eligible:
        result = city_specialists.backtest(prices)
        assert result["equity"][-1]["date"] == "2025-07-20"
    else:
        with pytest.raises(CityError, match="dates.*passées ou présentes"):
            city_specialists.backtest(prices)
