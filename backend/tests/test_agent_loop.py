from app.main import process_market_cycle
from app.agent_loop import run_cycle
from app.risk_engine import RiskEngine
from app.performance import calculate_unrealized_pnl
from app.strategy import activate_strategy, build_signal_from_ticker, get_active_strategy_id
import asyncio


class FakeMarketService:
    def fetch_spot_ticker(self, symbol: str):
        return {
            "symbol": symbol,
            "last_price": 110.0,
            "open_price": 100.0,
            "status": "live",
        }


class FakeFallbackService:
    def fetch_spot_ticker(self, symbol: str):
        return {
            "symbol": symbol,
            "status": "fallback",
            "error": "network unavailable",
        }


def test_process_market_cycle_generates_live_decision_and_trade():
    result = process_market_cycle(
        "AAPLUSDT",
        market_service=FakeMarketService(),
        risk_engine=RiskEngine(),
    )

    assert result["decision"]["action"] == "buy"
    assert result["risk_check"]["allowed"] is True
    assert result["log_entry"]["type"] == "trade"


def test_process_market_cycle_uses_strategy_size_and_leverage(monkeypatch):
    monkeypatch.setattr(
        "app.main.build_signal_from_ticker",
        lambda ticker: {
            "action": "buy",
            "size": 2.0,
            "leverage": 2.0,
            "reason": "test strategy",
            "signal_strength": 0.5,
            "status": "logged",
        },
    )

    result = process_market_cycle(
        "AAPLUSDT",
        market_service=FakeMarketService(),
        risk_engine=RiskEngine(),
    )

    assert result["risk_check"]["risk"]["notional"] == 220.0
    assert result["risk_check"]["risk"]["leverage"] == 2.0


def test_process_market_cycle_handles_fallback_without_trade():
    result = process_market_cycle(
        "AAPLUSDT",
        market_service=FakeFallbackService(),
        risk_engine=RiskEngine(),
    )

    assert result["decision"]["action"] == "hold"
    assert result["log_entry"]["type"] == "market_data"


def test_strategy_activation_changes_signal_behavior():
    activate_strategy("mean_reversion")
    try:
        result = build_signal_from_ticker(
            {"status": "live", "last_price": 102.0, "open_price": 100.0}
        )
        assert result["action"] == "sell"
        assert get_active_strategy_id() == "mean_reversion"
    finally:
        activate_strategy("momentum_breakout")


class FakeExecutionClient:
    def __init__(self):
        self.trades = []

    def place_market_order(self, trade):
        self.trades.append(trade)
        return {"status": "submitted", "order_id": "paper-loop-1"}


class FakeCycleLogger:
    def __init__(self, has_open_position=True):
        self.has_open_position_value = has_open_position

    def has_open_position(self, symbol):
        return self.has_open_position_value

    def log_cycle(self, result):
        return {"status": "logged"}


class LivePositionsExecutionClient(FakeExecutionClient):
    def __init__(self, positions):
        super().__init__()
        self.positions = positions

    def fetch_futures_positions(self):
        return {"status": "ok", "positions": self.positions}

    def flash_close_position(self, symbol, position_side):
        self.closed = {"symbol": symbol, "position_side": position_side}
        return {"status": "submitted", "order_id": "close-1"}


def test_agent_cycle_runs_signal_risk_intent_and_execution():
    execution = FakeExecutionClient()
    result = asyncio.run(
        run_cycle(
            "AAPLUSDT",
            market_service=FakeMarketService(),
            risk_engine=RiskEngine(),
            execution_client=execution,
        )
    )

    assert result["status"] == "submitted"
    assert result["risk_check"]["allowed"] is True
    assert result["intent"]["intent_hash"]
    assert execution.trades[0]["market"] == "futures"


def test_agent_cycle_uses_strategy_decision_size_and_leverage(monkeypatch):
    monkeypatch.setattr(
        "app.agent_loop.build_signal_from_ticker",
        lambda ticker: {
            "action": "buy",
            "size": 2.0,
            "leverage": 2.0,
            "reason": "test strategy",
            "signal_strength": 0.5,
            "status": "logged",
        },
    )
    execution = FakeExecutionClient()
    result = asyncio.run(
        run_cycle(
            "AAPLUSDT",
            market_service=FakeMarketService(),
            risk_engine=RiskEngine(),
            execution_client=execution,
        )
    )

    assert result["status"] == "submitted"
    assert execution.trades[0]["qty"] == 2.0
    assert execution.trades[0]["leverage"] == 2.0


def test_agent_cycle_uses_selected_spot_market():
    execution = FakeExecutionClient()
    result = asyncio.run(
        run_cycle(
            "AAPLUSDT",
            market_service=FakeMarketService(),
            risk_engine=RiskEngine(),
            execution_client=execution,
            market_type="spot",
        )
    )

    assert result["status"] == "submitted"
    assert execution.trades[0]["market"] == "spot"


def test_agent_cycle_autonomously_selects_spot_for_one_x_signal():
    execution = FakeExecutionClient()
    result = asyncio.run(
        run_cycle(
            "AAPLUSDT",
            market_service=FakeMarketService(),
            risk_engine=RiskEngine(),
            execution_client=execution,
            market_type="autonomous",
        )
    )

    assert result["status"] == "submitted"
    assert result["decision"]["market"] == "spot"
    assert execution.trades[0]["market"] == "spot"


def test_agent_cycle_autonomously_selects_futures_for_strong_signal():
    class StrongMarketService:
        def fetch_spot_ticker(self, symbol):
            return {"symbol": symbol, "last_price": 180.0, "open_price": 100.0, "status": "live"}

    execution = FakeExecutionClient()
    result = asyncio.run(
        run_cycle(
            "AAPLUSDT",
            market_service=StrongMarketService(),
            risk_engine=RiskEngine(),
            execution_client=execution,
            market_type="autonomous",
        )
    )

    assert result["status"] == "submitted"
    assert result["decision"]["market"] == "futures"
    assert execution.trades[0]["market"] == "futures"


def test_agent_cycle_does_not_execute_hold_signal():
    class FlatMarketService:
        def fetch_spot_ticker(self, symbol):
            return {"symbol": symbol, "last_price": 100.0, "open_price": 100.0, "status": "live"}

    execution = FakeExecutionClient()
    result = asyncio.run(
        run_cycle(
            "AAPLUSDT",
            market_service=FlatMarketService(),
            risk_engine=RiskEngine(),
            execution_client=execution,
        )
    )

    assert result["status"] == "logged"
    assert execution.trades == []


def test_agent_cycle_uses_empty_live_positions_over_stale_logger():
    execution = LivePositionsExecutionClient([])
    result = asyncio.run(
        run_cycle(
            "AAPLUSDT",
            market_service=FakeMarketService(),
            risk_engine=RiskEngine(),
            execution_client=execution,
            cycle_logger=FakeCycleLogger(has_open_position=True),
        )
    )

    assert result["status"] == "submitted"
    assert len(execution.trades) == 1


def test_agent_cycle_skips_when_live_position_exists():
    execution = LivePositionsExecutionClient([{"symbol": "AAPLUSDT", "total": "1", "holdSide": "long", "openPriceAvg": "111", "unrealizedPL": "-1"}])
    result = asyncio.run(
        run_cycle(
            "AAPLUSDT",
            market_service=FakeMarketService(),
            risk_engine=RiskEngine(),
            execution_client=execution,
            cycle_logger=FakeCycleLogger(has_open_position=False),
        )
    )

    assert result["status"] == "skipped_existing_position"
    assert execution.trades == []


def test_agent_cycle_adds_to_profitable_same_direction_position():
    execution = LivePositionsExecutionClient(
        [
            {
                "symbol": "AAPLUSDT",
                "total": "1",
                "holdSide": "long",
                "openPriceAvg": "108",
                "unrealizedPL": "1",
            }
        ]
    )
    result = asyncio.run(
        run_cycle(
            "AAPLUSDT",
            market_service=FakeMarketService(),
            risk_engine=RiskEngine(max_position_size=250),
            execution_client=execution,
        )
    )

    assert result["status"] == "submitted"
    assert len(execution.trades) == 1
    assert result["risk_check"]["risk"]["notional"] == 110.0


def test_agent_cycle_closes_position_at_take_profit(monkeypatch):
    monkeypatch.setattr("app.agent_loop.TAKE_PROFIT_PCT", 5.0)
    execution = LivePositionsExecutionClient(
        [{"symbol": "AAPLUSDT", "total": "1", "holdSide": "long", "openPriceAvg": "100", "unrealizedPL": "6"}]
    )

    result = asyncio.run(
        run_cycle("AAPLUSDT", market_service=FakeMarketService(), risk_engine=RiskEngine(), execution_client=execution)
    )

    assert result["status"] == "closed"
    assert result["exit_reason"] == "take_profit"
    assert execution.closed["position_side"] == "buy"


def test_agent_cycle_closes_position_on_opposite_signal(monkeypatch):
    monkeypatch.setattr("app.agent_loop.CLOSE_ON_SIGNAL_VIOLATION", True)
    monkeypatch.setattr("app.agent_loop.TAKE_PROFIT_PCT", 50.0)
    monkeypatch.setattr(
        "app.agent_loop.build_signal_from_ticker",
        lambda ticker: {"action": "sell", "size": 1.0, "leverage": 1.0, "signal_strength": 0.5, "reason": "reversal"},
    )
    execution = LivePositionsExecutionClient(
        [{"symbol": "AAPLUSDT", "total": "1", "holdSide": "long", "openPriceAvg": "100", "unrealizedPL": "1"}]
    )

    result = asyncio.run(
        run_cycle("AAPLUSDT", market_service=FakeMarketService(), risk_engine=RiskEngine(), execution_client=execution)
    )

    assert result["status"] == "closed"
    assert result["exit_reason"] == "signal_violation"


def test_calculate_unrealized_pnl_for_long_and_short_cycles():
    cycles = [
        {
            "symbol": "AAPLUSDT",
            "status": "submitted",
            "decision": {"action": "buy"},
            "ticker": {"last_price": 100},
            "risk_check": {"risk": {"notional": 1000}},
        },
        {
            "symbol": "TSLAUSDT",
            "status": "submitted",
            "decision": {"action": "sell"},
            "ticker": {"last_price": 200},
            "risk_check": {"risk": {"notional": 1000}},
        },
    ]

    marks = {"AAPLUSDT": 110, "TSLAUSDT": 190}
    result = calculate_unrealized_pnl(
        cycles,
        mark_fetcher=lambda symbol: {"status": "live", "last_price": marks[symbol]},
    )

    assert result["unrealized_pnl"] == 150.0
    assert result["open_positions"][0]["qty"] == 10.0


def test_calculate_pnl_moves_closed_position_to_realized():
    cycles = [
        {
            "symbol": "AAPLUSDT",
            "status": "submitted",
            "decision": {"action": "buy"},
            "ticker": {"last_price": 100},
            "risk_check": {"risk": {"notional": 1000}},
        },
        {
            "symbol": "AAPLUSDT",
            "status": "closed",
            "decision": {"action": "close", "closed_position_side": "buy"},
            "ticker": {"last_price": 110},
            "order_result": {
                "trade_side": "close",
                "closed_position_side": "buy",
                "qty": 10,
                "entry_price": 110,
            },
        },
    ]

    result = calculate_unrealized_pnl(
        cycles,
        mark_fetcher=lambda symbol: {"status": "live", "last_price": 110},
    )

    assert result["realized_pnl"] == 100.0
    assert result["unrealized_pnl"] == 0.0
    assert result["open_positions"] == []
