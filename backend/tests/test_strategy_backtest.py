from app.strategy import backtest_strategy


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
    assert set(result["metrics"]).issuperset({"return", "win_rate", "sharpe_ratio", "max_drawdown"})
