from app.strategy import backtest_strategy
import pytest


def test_backtest_strategy_returns_shared_metrics_response():
    candles = [
        {"open": 100.0, "close": 99.0, "high": 101.0, "low": 98.0},
        {"open": 99.0, "close": 101.0, "high": 102.0, "low": 98.0},
        {"open": 101.0, "close": 100.0, "high": 102.5, "low": 99.0},
    ]

    result = backtest_strategy("mean_reversion", candles)

    assert result["strategy_id"] == "mean_reversion"
    assert result["status"] == "completed"
    assert result["candles_analyzed"] == 3
    assert set(result["metrics"]).issuperset({"return", "win_rate", "sharpe_ratio", "max_drawdown", "deflated_sharpe_ratio"})


def test_backtest_position_sizing_uses_sub_dollar_price():
    result = backtest_strategy("mean_reversion", [
        {"open": 0.50, "close": 0.45, "high": 0.51, "low": 0.44},
        {"open": 0.45, "close": 0.60, "high": 0.61, "low": 0.44},
    ])

    assert result["status"] == "completed"


def test_backtest_rejects_unsupported_strategies():
    with pytest.raises(ValueError, match="not backtestable"):
        backtest_strategy("pairs_trading", [{"open": 100, "close": 101}])
