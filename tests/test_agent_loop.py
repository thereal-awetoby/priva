from app.main import process_market_cycle
from app.risk_engine import RiskEngine


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
