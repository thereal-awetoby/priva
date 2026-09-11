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


def test_trade_rejected_when_symbol_is_not_allowed():
    engine = RiskEngine(allowed_symbols=["AAPLUSDT", "TSLAUSDT"])
    trade = {
        "symbol": "MSFTUSDT",
        "side": "buy",
        "qty": 1,
        "entry_price": 100,
        "leverage": 1,
    }

    result = engine.evaluate_trade(
        trade=trade,
        current_positions=[],
        current_daily_pnl=0,
    )

    assert result["allowed"] is False
    assert "unsupported_symbol" in result["reasons"][0]


def test_update_settings_reconfigures_risk_limits_and_allowed_symbols():
    engine = RiskEngine()

    settings = engine.update_settings({
        "max_position_size": 1000,
        "max_daily_loss": 200,
        "max_leverage": 3,
        "allowed_symbols": ["AAPLUSDT"],
    })

    assert settings["max_position_size"] == 1000
    assert settings["max_daily_loss"] == 200
    assert settings["max_leverage"] == 3
    assert settings["allowed_symbols"] == ["AAPLUSDT"]
