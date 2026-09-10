from app.risk_engine import RiskEngine


def test_trade_allowed_when_within_limits():
    engine = RiskEngine()
    trade = {
        "symbol": "AAPLUSDT",
        "side": "buy",
        "qty": 5,
        "entry_price": 220,
        "leverage": 2,
    }

    result = engine.evaluate_trade(
        trade=trade,
        current_positions=[],
        current_daily_pnl=120,
    )

    assert result["allowed"] is True
    assert result["reasons"] == []


def test_trade_rejected_when_position_size_exceeds_limit():
    engine = RiskEngine()
    trade = {
        "symbol": "NVDAUSDT",
        "side": "buy",
        "qty": 200,
        "entry_price": 160,
        "leverage": 1,
    }

    result = engine.evaluate_trade(
        trade=trade,
        current_positions=[],
        current_daily_pnl=100,
    )

    assert result["allowed"] is False
    assert "max_position_size" in result["reasons"][0]


def test_trade_rejected_when_daily_loss_limit_hit():
    engine = RiskEngine()
    trade = {
        "symbol": "MSFTUSDT",
        "side": "sell",
        "qty": 10,
        "entry_price": 300,
        "leverage": 2,
    }

    result = engine.evaluate_trade(
        trade=trade,
        current_positions=[],
        current_daily_pnl=-1600,
    )

    assert result["allowed"] is False
    assert "max_daily_loss" in result["reasons"][0]
