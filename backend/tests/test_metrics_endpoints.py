from app import main


class EmptyExecutionClient:
    def fetch_futures_positions(self):
        return {"status": "ok", "positions": []}


class ActiveExecutionClient:
    def fetch_futures_positions(self):
        return {
            "status": "ok",
            "positions": [
                {
                    "symbol": "AAPLUSDT",
                    "holdSide": "long",
                    "total": "1",
                    "openPriceAvg": "320",
                    "markPrice": "325",
                    "openCost": "320",
                    "unrealizedPL": "5",
                    "leverage": "1",
                    "marginMode": "isolated",
                }
            ],
        }


def test_pnl_uses_live_positions_and_zero_realized_without_cycles(monkeypatch):
    monkeypatch.setattr(main, "paper_execution_client", EmptyExecutionClient())
    monkeypatch.setattr(main.cycle_logger, "fetch_cycles", lambda **kwargs: [])

    result = main.pnl()

    assert result["unrealized_pnl"] == 0.0
    assert result["realized_pnl"] == 0.0
    assert result["total_pnl"] == 0.0
    assert result["source"] == "bitget_and_supabase"


def test_risk_usage_reflects_live_position(monkeypatch):
    monkeypatch.setattr(main, "paper_execution_client", ActiveExecutionClient())
    monkeypatch.setattr(main.cycle_logger, "fetch_cycles", lambda **kwargs: [])

    result = main.risk_usage()

    assert result["current_position_size"] == 320.0
    assert result["current_leverage"] == 1.0
    assert result["usage_percent"]["position_size"] == 1.28
    assert result["positions"][0]["symbol"] == "AAPLUSDT"
