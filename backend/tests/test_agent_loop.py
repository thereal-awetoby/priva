from app.main import process_market_cycle
from app.agent_loop import run_cycle
from app.risk_engine import RiskEngine
from app.performance import calculate_unrealized_pnl
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


def test_process_market_cycle_handles_fallback_without_trade():
    result = process_market_cycle(
        "AAPLUSDT",
        market_service=FakeFallbackService(),
        risk_engine=RiskEngine(),
    )

    assert result["decision"]["action"] == "hold"
    assert result["log_entry"]["type"] == "market_data"


class FakeExecutionClient:
    def __init__(self):
        self.trades = []

    def place_market_order(self, trade):
        self.trades.append(trade)
        return {"status": "submitted", "order_id": "paper-loop-1"}


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
