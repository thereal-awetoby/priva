import asyncio

from app import main
from app.agent_loop import run_cycle
from app.auth import AuthenticatedUser
from app.balance_snapshots import fetch_combined_balance_snapshot


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


class BalanceExecutionClient:
    def __init__(self, equity):
        self.equity = equity

    def fetch_futures_account_balance(self):
        return {"status": "ok", "equity": self.equity, "available": self.equity}

    def fetch_spot_assets(self):
        return {"status": "ok", "assets": []}


class CombinedBalanceExecutionClient(BalanceExecutionClient):
    def fetch_spot_assets(self):
        return {
            "status": "ok",
            "assets": [
                {"coin": "USDT", "available": "500"},
                {"coin": "AAPL", "total": "2"},
            ],
        }


class BalanceMarketService:
    def fetch_spot_ticker(self, symbol):
        return {"status": "live", "last_price": 100.0}


class SnapshotMarketService(BalanceMarketService):
    def fetch_spot_ticker(self, symbol):
        return {"status": "live", "last_price": 110.0, "open_price": 100.0}


class SnapshotExecutionClient:
    def __init__(self, configured=True):
        self.configured = configured
        self.trades = []
        self.session = None

    def fetch_futures_account_balance(self):
        if not self.configured:
            return {"status": "not_configured"}
        return {"status": "ok", "equity": 1200.0}

    def fetch_spot_assets(self):
        if not self.configured:
            return {"status": "not_configured"}
        return {"status": "ok", "assets": [{"coin": "USDT", "available": "300"}]}

    def place_market_order(self, trade):
        self.trades.append(trade)
        return {"status": "submitted", "order_id": "test-order"}

    def configure_credentials(self, *values):
        return None


class SnapshotLogger:
    def __init__(self):
        self.snapshots = []

    def log_cycle(self, result):
        return {"status": "logged"}

    def log_balance_snapshot(self, snapshot):
        self.snapshots.append(snapshot)
        return {"status": "logged"}

    def has_open_position(self, symbol, market=None):
        return False


def test_combined_balance_snapshot_contains_both_markets():
    snapshot = fetch_combined_balance_snapshot(
        CombinedBalanceExecutionClient(1000.0),
        BalanceMarketService(),
    )

    assert snapshot["futures_equity"] == 1000.0
    assert snapshot["spot_equity"] == 700.0
    assert snapshot["balance"] == 1700.0


def test_agent_cycle_persists_combined_snapshot_end_to_end():
    logger = SnapshotLogger()
    result = asyncio.run(
        run_cycle(
            "AAPLUSDT",
            market_service=SnapshotMarketService(),
            risk_engine=main.risk_engine,
            execution_client=SnapshotExecutionClient(),
            cycle_logger=logger,
        )
    )

    assert result["status"] == "submitted"
    assert len(logger.snapshots) == 1
    assert logger.snapshots[0]["futures_equity"] == 1200.0
    assert logger.snapshots[0]["spot_equity"] == 300.0


def test_agent_cycle_does_not_persist_unconfigured_snapshot():
    logger = SnapshotLogger()
    asyncio.run(
        run_cycle(
            "AAPLUSDT",
            market_service=BalanceMarketService(),
            risk_engine=main.risk_engine,
            execution_client=SnapshotExecutionClient(configured=False),
            cycle_logger=logger,
        )
    )

    assert logger.snapshots == []


def test_connection_handler_persists_combined_snapshot(monkeypatch):
    logger = SnapshotLogger()
    execution = SnapshotExecutionClient()

    class Candidate(SnapshotExecutionClient):
        def fetch_account_mode(self, symbol):
            return {"status": "ok", "position_mode": "hedge"}

    monkeypatch.setattr(main, "BitgetPaperExecutionClient", lambda session=None: Candidate())
    monkeypatch.setattr(main, "execution_client_for", lambda user: execution)
    monkeypatch.setattr(main, "cycle_logger_for", lambda user: logger)
    monkeypatch.setattr(main, "paper_execution_client", execution)
    monkeypatch.setattr(main.supabase_auth, "required", False)

    result = asyncio.run(
        main.connect_bitget(
            main.BitgetConnectionRequest(api_key="key", api_secret="secret", passphrase="pass"),
            AuthenticatedUser("local-development"),
        )
    )

    assert result["status"] == "connected"
    assert len(logger.snapshots) == 1
    assert logger.snapshots[0]["futures_equity"] == 1200.0
    assert logger.snapshots[0]["spot_equity"] == 300.0


def test_connection_handler_does_not_persist_unconfigured_snapshot(monkeypatch):
    logger = SnapshotLogger()
    execution = SnapshotExecutionClient(configured=False)

    class Candidate(SnapshotExecutionClient):
        def fetch_account_mode(self, symbol):
            return {"status": "ok", "position_mode": "hedge"}

    monkeypatch.setattr(main, "BitgetPaperExecutionClient", lambda session=None: Candidate())
    monkeypatch.setattr(main, "execution_client_for", lambda user: execution)
    monkeypatch.setattr(main, "cycle_logger_for", lambda user: logger)
    monkeypatch.setattr(main, "paper_execution_client", execution)
    monkeypatch.setattr(main.supabase_auth, "required", False)

    result = asyncio.run(
        main.connect_bitget(
            main.BitgetConnectionRequest(api_key="key", api_secret="secret", passphrase="pass"),
            AuthenticatedUser("local-development"),
        )
    )

    assert result["status"] == "connected"
    assert logger.snapshots == []


def test_pnl_uses_live_positions_and_zero_realized_without_cycles(monkeypatch):
    monkeypatch.setattr(main, "paper_execution_client", EmptyExecutionClient())
    monkeypatch.setattr(main.cycle_logger, "fetch_cycles", lambda **kwargs: [])

    result = main.pnl()

    assert result["unrealized_pnl"] == 0.0
    assert result["realized_pnl"] == 0.0
    assert result["total_pnl"] == 0.0
    assert result["source"] == "bitget_and_supabase"


def test_account_balance_reports_daily_change_percent(monkeypatch):
    main._daily_balance_baselines.clear()
    client = BalanceExecutionClient(1000.0)
    monkeypatch.setattr(main, "paper_execution_client", client)

    first = main.account_balance()
    assert first["starting_balance"] == 1000.0
    assert first["daily_change_pct"] == 0.0

    client.equity = 1100.0
    second = main.account_balance()
    assert second["daily_change"] == 100.0
    assert second["daily_change_pct"] == 10.0
    assert second["balance"] == 1100.0
    assert second["futures_equity"] == 1100.0


def test_account_balance_history_exposes_equity_curve_summary(monkeypatch):
    main._balance_history.clear()
    monkeypatch.setattr(main.cycle_logger, "fetch_balance_snapshots", lambda **kwargs: [])
    monkeypatch.setattr(main.agent_loop, "recent_balance_snapshots", lambda: [])
    main._balance_history.extend(
        [
            {"timestamp": "2026-09-20T00:00:00Z", "balance": 1000.0, "equity": 1000.0},
            {"timestamp": "2026-09-23T13:42:00Z", "balance": 1000.0, "equity": 1000.0},
            {"timestamp": "2026-09-23T13:52:00Z", "balance": 1100.0, "equity": 1100.0},
        ]
    )

    result = main.account_balance_history()

    assert result["status"] == "ok"
    assert result["starting_balance"] == 1000.0
    assert result["latest_balance"] == 1100.0
    assert result["point_count"] == 2
    assert result["points"][0]["timestamp"] == "2026-09-23T13:42:00Z"


def test_account_balance_combines_futures_and_spot_equity(monkeypatch):
    main._daily_balance_baselines.clear()
    monkeypatch.setattr(main, "paper_execution_client", CombinedBalanceExecutionClient(1000.0))
    monkeypatch.setattr(main, "market_service", BalanceMarketService())

    result = main.account_balance()

    assert result["futures_equity"] == 1000.0
    assert result["spot_usdt"] == 500.0
    assert result["spot_equity"] == 700.0
    assert result["balance"] == 1700.0
    assert result["spot_holdings"] == [
        {"coin": "AAPL", "quantity": 2.0, "mark_price": 100.0, "value_usd": 200.0}
    ]


def test_trade_metrics_detect_real_drawdown_from_closed_pnl(monkeypatch):
    cycles = [
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
            "symbol": "TSLAUSDT",
            "decision": {"action": "buy"},
            "ticker": {"last_price": 100.0},
            "risk_check": {"risk": {"notional": 1000.0}},
        },
        {
            "created_at": "2026-09-10T00:03:00Z",
            "status": "closed",
            "symbol": "TSLAUSDT",
            "decision": {"action": "close", "closed_position_side": "buy"},
            "ticker": {"last_price": 90.0},
            "order_result": {"closed_position_side": "buy", "qty": 10.0, "entry_price": 90.0},
        },
        {
            "created_at": "2026-09-10T00:04:00Z",
            "status": "submitted",
            "symbol": "NVDAUSDT",
            "decision": {"action": "buy"},
            "ticker": {"last_price": 100.0},
            "risk_check": {"risk": {"notional": 1000.0}},
        },
        {
            "created_at": "2026-09-10T00:05:00Z",
            "status": "closed",
            "symbol": "NVDAUSDT",
            "decision": {"action": "close", "closed_position_side": "buy"},
            "ticker": {"last_price": 105.0},
            "order_result": {"closed_position_side": "buy", "qty": 10.0, "entry_price": 105.0},
        },
    ]

    metrics = main._trade_metrics(cycles, 10000.0)

    assert metrics["win_rate_pct"] == 66.67
    assert metrics["max_drawdown_pct"] == 0.99


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
    assert result["entries"][0]["opened_at"] is None


def test_activity_log_labels_closed_cycle_as_close(monkeypatch):
    monkeypatch.setattr(
        main.cycle_logger,
        "fetch_cycles",
        lambda **kwargs: [
            {
                "created_at": "2026-09-22T19:55:02Z",
                "symbol": "AAPLUSDT",
                "status": "closed",
                "decision": {"action": "sell"},
                "order_result": {"order_id": "close-1"},
            }
        ],
    )

    result = main.activity_log()

    assert result["entries"][0]["action"] == "close"


def test_activity_log_adds_readable_labels_categories_and_intent_hash(monkeypatch):
    monkeypatch.setattr(
        main.cycle_logger,
        "fetch_cycles",
        lambda **kwargs: [
            {
                "created_at": "2026-09-22T19:55:02Z",
                "symbol": "AAPLUSDT",
                "status": "risk_rejected",
                "decision": {"action": "buy"},
                "risk_check": {
                    "allowed": False,
                    "reasons": ["max_position_size:26000.0>25000", "max_leverage:6.0>5"],
                },
                "intent": {"intent_hash": "1234567890abcdef"},
            },
            {
                "created_at": "2026-09-22T19:56:02Z",
                "symbol": "AAPLUSDT",
                "status": "logged",
                "decision": {"action": "hold"},
                "risk_check": {"allowed": False, "reasons": ["no_trade_signal"]},
            },
        ],
    )

    entries = main.activity_log()["entries"]
    rejected, evaluation = entries

    assert rejected["display_label"] == "Risk rejected · Max position size exceeded ($26,000.00 > $25,000.00); Max leverage exceeded (6x > 5x)"
    assert rejected["display_detail"] == "Max position size exceeded ($26,000.00 > $25,000.00); Max leverage exceeded (6x > 5x)"
    assert rejected["category"] == "event"
    assert rejected["intent_hash"] == "1234567890abcdef"
    assert rejected["intent_hash_short"] == "12345678…"
    assert evaluation["display_label"] == "Evaluating · no signal"
    assert evaluation["display_detail"] == "No trade signal"
    assert evaluation["category"] == "evaluation"
    assert "intent_hash" not in evaluation
    assert "intent_hash_short" not in evaluation


def test_activity_log_humanizes_blocked_reasons_and_skips_nothing_to_sell(monkeypatch):
    monkeypatch.setattr(
        main.cycle_logger,
        "fetch_cycles",
        lambda **kwargs: [
            {
                "created_at": "2026-09-22T19:57:02Z",
                "symbol": "AAPLUSDT",
                "market": "spot",
                "status": "blocked",
                "decision": {"action": "buy"},
                "reason": "spot_ticker_unavailable",
            },
            {
                "created_at": "2026-09-22T19:58:02Z",
                "symbol": "TSLAUSDT",
                "market": "spot",
                "status": "logged",
                "decision": {"action": "sell"},
                "reason": "no_spot_position_to_close",
            },
        ],
    )

    blocked, skipped = main.activity_log()["entries"]

    assert blocked["display_detail"] == "spot ticker unavailable"
    assert blocked["display_label"] == "Blocked · spot ticker unavailable"
    assert blocked["category"] == "event"
    assert skipped["display_detail"] == "nothing to sell"
    assert skipped["display_label"] == "Skipped · nothing to sell"
    assert skipped["category"] == "event"


def test_status_reports_live_cycle_and_risk_usage(monkeypatch):
    monkeypatch.setattr(
        main.user_runtime_registry,
        "status",
        lambda user_id: {
            "running": True,
            "symbols": ["TSLAUSDT"],
            "cycle_interval_seconds": 45,
            "workers": {
                "autonomous:spot": {
                    "last_cycle_at": "2026-09-24T12:00:00+00:00",
                },
            },
        },
    )
    monkeypatch.setattr(
        main,
        "risk_usage",
        lambda user: {"usage_percent": {"daily_loss": 42.5}},
    )

    result = main.status()

    assert result["watched_symbols"] == ["TSLAUSDT"]
    assert result["last_cycle"] == "2026-09-24T12:00:00+00:00"
    assert result["cycle_interval_seconds"] == 45
    assert result["daily_loss_usage_pct"] == 42.5
    assert result["agent_state"] == "online"

    monkeypatch.setattr(
        main.user_runtime_registry,
        "status",
        lambda user_id: {"running": False, "symbols": [], "workers": {}, "cycle_interval_seconds": None},
    )
    assert main.status()["agent_state"] == "offline"


def test_agent_settings_can_switch_autonomous_market():
    original_market = main.agent_loop.MARKET_TYPE
    try:
        assert main.agent_settings()["market"] == original_market
        result = main.update_agent_settings(main.AgentSettingsRequest(market="spot"))
        assert result["status"] == "updated"
        assert result["market"] == "spot"
        assert main.agent_settings()["market"] == "spot"
    finally:
        main.agent_loop.configure_market_type(original_market)


def test_agent_settings_updates_exit_rules():
    original = main.agent_loop.get_exit_rules()
    try:
        result = main.update_agent_settings(
            main.AgentSettingsRequest(
                market="futures",
                take_profit_pct=6.0,
                stop_loss_pct=2.5,
                close_on_signal_violation=False,
            )
        )
        assert result["take_profit_pct"] == 6.0
        assert result["stop_loss_pct"] == 2.5
        assert result["close_on_signal_violation"] is False
    finally:
        main.agent_loop.configure_exit_rules(**original)


def test_activity_log_exposes_trade_open_time(monkeypatch):
    opened_at = "2026-09-14T12:34:56Z"
    monkeypatch.setattr(
        main.cycle_logger,
        "fetch_cycles",
        lambda **kwargs: [
            {
                "created_at": opened_at,
                "symbol": "AAPLUSDT",
                "status": "submitted",
                "order_result": {"order_id": "order-1"},
            }
        ],
    )

    result = main.activity_log()

    assert result["entries"][0]["opened_at"] == opened_at


def test_positions_derives_open_time_from_all_modes_and_preserves_open_state(monkeypatch):
    class AccumulatedPositionClient:
        def fetch_futures_positions(self):
            return {
                "status": "ok",
                "positions": [{
                    "symbol": "AAPLUSDT",
                    "holdSide": "short",
                    "total": "3",
                    "openPriceAvg": "340",
                    "markPrice": "338",
                }],
            }

    monkeypatch.setattr(main, "paper_execution_client", AccumulatedPositionClient())
    monkeypatch.setattr(
        main.cycle_logger,
        "fetch_cycles",
        lambda **kwargs: [
            {
                "created_at": "2026-09-23T13:33:28.497903+00:00",
                "symbol": "AAPLUSDT",
                "market": "futures",
                "mode": "strategy",
                "status": "submitted",
                "decision": {"action": "sell"},
                "order_result": {"trade_side": "open", "side": "sell", "qty": 1},
            },
            {
                "created_at": "2026-09-23T13:40:00+00:00",
                "symbol": "AAPLUSDT",
                "market": "futures",
                "mode": "autonomous",
                "status": "submitted",
                "decision": {"action": "sell"},
                "order_result": {"trade_side": "open", "side": "sell", "qty": 2},
            },
        ],
    )

    result = main.positions()

    position = result["positions"][0]
    assert position["opened_at"] == "2026-09-23T13:33:28.497903+00:00"
    assert position["opened_at_source"] == "ledger"
    assert position["closed_at"] is None


def test_real_aapl_qty_29_fixture_walks_back_interleaved_modes():
    user_id = "test-user"
    timestamps_and_modes = [
        ("2026-09-23T13:33:28.497903+00:00", "strategy"),
        ("2026-09-23T13:35:22.560384+00:00", "autonomous"),
        ("2026-09-23T13:35:22.561809+00:00", "strategy"),
        ("2026-09-23T13:40:29.384671+00:00", "strategy"),
        ("2026-09-23T13:40:30.105329+00:00", "autonomous"),
        ("2026-09-23T13:42:23.828144+00:00", "autonomous"),
        ("2026-09-23T13:42:23.830403+00:00", "strategy"),
        ("2026-09-23T13:47:34.265479+00:00", "strategy"),
        ("2026-09-23T13:47:34.889761+00:00", "autonomous"),
        ("2026-09-23T13:48:11.645146+00:00", "autonomous"),
        ("2026-09-23T13:48:11.647076+00:00", "strategy"),
        ("2026-09-23T13:53:22.561022+00:00", "strategy"),
        ("2026-09-23T13:53:25.605605+00:00", "autonomous"),
        ("2026-09-23T13:58:29.211795+00:00", "strategy"),
        ("2026-09-23T13:58:35.333208+00:00", "autonomous"),
        ("2026-09-23T17:06:27.204921+00:00", "autonomous"),
        ("2026-09-23T17:07:38.899201+00:00", "autonomous"),
        ("2026-09-23T17:12:52.086824+00:00", "autonomous"),
        ("2026-09-23T17:16:49.961145+00:00", "autonomous"),
        ("2026-09-23T17:18:48.155158+00:00", "autonomous"),
        ("2026-09-23T17:22:41.870481+00:00", "autonomous"),
        ("2026-09-23T17:27:43.638659+00:00", "autonomous"),
        ("2026-09-23T17:30:38.198127+00:00", "strategy"),
        ("2026-09-23T17:31:29.509135+00:00", "strategy"),
        ("2026-09-23T17:31:38.717360+00:00", "strategy"),
        ("2026-09-23T17:36:42.076063+00:00", "strategy"),
        ("2026-09-23T17:41:45.312737+00:00", "strategy"),
        ("2026-09-23T18:38:50.219618+00:00", "strategy"),
        ("2026-09-23T18:43:50.480805+00:00", "autonomous"),
    ]
    cycles = [
        {
            "created_at": created_at,
            "user_id": user_id,
            "symbol": "AAPLUSDT",
            "market": "futures",
            "mode": mode,
            "status": "submitted",
            "decision": {"action": "sell"},
            "order_result": {
                "trade_side": "open",
                "side": "sell",
                "qty": 1.0,
            },
        }
        for created_at, mode in timestamps_and_modes
    ]

    timestamp, source = main._derive_open_timestamp(
        {
            "user_id": user_id,
            "symbol": "AAPLUSDT",
            "holdSide": "short",
            "total": 29,
        },
        cycles,
    )

    assert len(cycles) == 29
    assert timestamp == "2026-09-23T13:33:28.497903+00:00"
    assert source == "ledger"


def test_skipped_existing_position_does_not_enter_open_timestamp_chain():
    timestamp, source = main._derive_open_timestamp(
        {"symbol": "AAPLUSDT", "holdSide": "short", "total": "1"},
        [{
            "created_at": "2026-09-23T13:33:28Z",
            "symbol": "AAPLUSDT",
            "market": "futures",
            "status": "skipped_existing_position",
            "decision": {"action": "sell"},
            "order_result": {"qty": 1, "side": "sell"},
        }],
    )

    assert timestamp is None
    assert source is None


def test_activity_log_exposes_close_time_without_open_time(monkeypatch):
    monkeypatch.setattr(
        main.cycle_logger,
        "fetch_cycles",
        lambda **kwargs: [{
            "created_at": "2026-09-23T13:33:25+00:00",
            "symbol": "AAPLUSDT",
            "status": "closed",
            "decision": {"action": "close", "closed_position_side": "sell"},
            "order_result": {
                "closed_position_side": "sell",
                "exchange": {"requestTime": "2026-09-23T13:33:26+00:00"},
            },
        }],
    )

    result = main.activity_log()

    assert result["entries"][0]["opened_at"] is None
    assert result["entries"][0]["closed_at"] == "2026-09-23T13:33:26+00:00"
