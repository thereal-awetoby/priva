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


def test_pnl_includes_trade_metrics(monkeypatch):
    monkeypatch.setattr(main, "paper_execution_client", EmptyExecutionClient())
    monkeypatch.setattr(
        main.cycle_logger,
        "fetch_cycles",
        lambda **kwargs: [
            {
                "created_at": "2026-09-10T00:00:00Z",
                "status": "submitted",
                "symbol": "AAPLUSDT",
                "decision": {"action": "buy"},
                "ticker": {"last_price": 100.0},
                "risk_check": {"risk": {"notional": 1000.0}},
            },
            {
                "created_at": "2026-09-10T00:01:00Z",
                "status": "closed",
                "symbol": "AAPLUSDT",
                "decision": {"action": "close", "closed_position_side": "buy"},
                "ticker": {"last_price": 110.0},
                "order_result": {"closed_position_side": "buy", "qty": 10.0, "entry_price": 110.0},
            },
            {
                "created_at": "2026-09-10T00:02:00Z",
                "status": "submitted",
                "symbol": "NVDAUSDT",
                "decision": {"action": "buy"},
                "ticker": {"last_price": 100.0},
                "risk_check": {"risk": {"notional": 1000.0}},
            },
            {
                "created_at": "2026-09-10T00:03:00Z",
                "status": "closed",
                "symbol": "NVDAUSDT",
                "decision": {"action": "close", "closed_position_side": "buy"},
                "ticker": {"last_price": 95.0},
                "order_result": {"closed_position_side": "buy", "qty": 10.0, "entry_price": 95.0},
            },
        ],
    )

    result = main.pnl()

    assert result["win_rate_pct"] == 50.0
    assert result["max_drawdown_pct"] == 0.0


def test_activity_log_includes_cycle_mode(monkeypatch):
    monkeypatch.setattr(
        main.cycle_logger,
        "fetch_cycles",
        lambda **kwargs: [
            {
                "created_at": "2026-09-10T00:00:00Z",
                "symbol": "AAPLUSDT",
                "status": "submitted",
                "mode": "strategy",
            }
        ],
    )

    result = main.activity_log()

    assert result["entries"][0]["mode"] == "strategy"
