from app.main import parse_strategy as parse_strategy_endpoint
from app import main
from app import strategy as strategy_module
from app.strategy import STRATEGY_CATALOG, build_pairs_signal, build_signal_from_ticker, configure_builtin_strategy, configure_symbol_strategies, get_active_strategy_id, list_strategy_catalog, parse_natural_language_strategy, parse_structured_strategy, register_custom_strategy, activate_strategy

import pytest


@pytest.fixture(autouse=True)
def isolated_strategy_state():
    original_strategies = dict(strategy_module.STRATEGIES)
    original_catalog = dict(strategy_module._registered_strategy_catalog)
    original_configs = {key: dict(value) for key, value in strategy_module._builtin_strategy_configs.items()}
    original_symbols = dict(strategy_module._symbol_strategy_ids)
    original_active = strategy_module._active_strategy_id
    yield
    strategy_module.STRATEGIES.clear()
    strategy_module.STRATEGIES.update(original_strategies)
    strategy_module._registered_strategy_catalog.clear()
    strategy_module._registered_strategy_catalog.update(original_catalog)
    strategy_module._builtin_strategy_configs.clear()
    strategy_module._builtin_strategy_configs.update({key: dict(value) for key, value in original_configs.items()})
    strategy_module._symbol_strategy_ids.clear()
    strategy_module._symbol_strategy_ids.update(original_symbols)
    strategy_module._active_strategy_id = original_active


def test_parse_natural_language_strategy_supports_mean_reversion_text():
    parsed = parse_natural_language_strategy("fade moves at least 1% away from the opening price")

    assert parsed["kind"] == "builtin"
    assert parsed["target_strategy"] == "mean_reversion"
    assert parsed["threshold_pct"] == 1.0


def test_parse_natural_language_strategy_supports_overnight_gap_text():
    parsed = parse_natural_language_strategy("fade overnight gaps larger than 2%")

    assert parsed["kind"] == "builtin"
    assert parsed["target_strategy"] == "overnight_gap"
    assert parsed["threshold_pct"] == 2.0


def test_overnight_gap_strategy_fades_gap_direction():
    activate_strategy("overnight_gap")
    try:
        gap_up = build_signal_from_ticker({
            "symbol": "AAPLUSDT",
            "status": "live",
            "last_price": 103.0,
            "previous_close": 100.0,
            "session_open": 103.0,
        })
        gap_down = build_signal_from_ticker({
            "symbol": "AAPLUSDT",
            "status": "live",
            "last_price": 97.0,
            "previous_close": 100.0,
            "session_open": 97.0,
        })

        assert gap_up["action"] == "sell"
        assert gap_down["action"] == "buy"
    finally:
        activate_strategy("momentum_breakout")


def test_pairs_signal_enters_opposite_legs_when_spread_is_extreme():
    first = [98, 99, 100, 101, 100, 120]
    second = [100, 100, 100, 100, 100, 100]

    signal = build_pairs_signal("AAPLUSDT", "TSLAUSDT", first, second, entry_zscore=2.0)

    assert signal["action"] == "enter_pair"
    assert signal["legs"] == [
        {"symbol": "AAPLUSDT", "side": "sell"},
        {"symbol": "TSLAUSDT", "side": "buy"},
    ]


def test_parse_structured_strategy_builds_custom_strategy_config():
    parsed = parse_structured_strategy({
        "action": "buy",
        "comparison": "open",
        "threshold_pct": 1.5,
    })

    assert parsed["kind"] == "custom"
    assert parsed["action"] == "buy"
    assert parsed["threshold_pct"] == 1.5


def test_parse_structured_strategy_supports_position_size():
    parsed = parse_structured_strategy({
        "action": "buy",
        "comparison": "open",
        "threshold_pct": 1.5,
        "position_size": 0.5,
    })

    assert parsed["kind"] == "custom"
    assert parsed["position_size"] == 0.5

    strategy_id = "custom_buy_open_150_0_5"
    register_custom_strategy(strategy_id, parsed)
    assert activate_strategy(strategy_id) is True

    ticker = {"status": "live", "last_price": 101.5, "open_price": 100.0}
    signal = build_signal_from_ticker(ticker)
    assert signal["size"] == 0.5


def test_parse_structured_strategy_supports_market_selection():
    parsed = parse_structured_strategy({
        "action": "buy",
        "comparison": "open",
        "threshold_pct": 1.5,
        "market": "spot",
    })

    assert parsed["market"] == "spot"


def test_custom_buy_and_sell_carry_trailing_profit_lock():
    payload = {
        "action": "buy",
        "comparison": "open",
        "threshold_pct": 1.0,
        "trailing_profit_lock_pct": 30,
    }
    parsed = parse_structured_strategy(payload)
    assert parsed["trailing_profit_lock_pct"] == 30.0

    buy_id = "custom_buy_lock_regression"
    register_custom_strategy(buy_id, parsed)
    buy_signal = build_signal_from_ticker(
        {"status": "live", "last_price": 102.0, "open_price": 100.0},
        strategy_id=buy_id,
    )
    assert buy_signal["trailing_profit_lock_pct"] == 30.0

    sell_id = "custom_sell_lock_regression"
    sell_parsed = parse_structured_strategy({**payload, "action": "sell"})
    register_custom_strategy(sell_id, sell_parsed)
    sell_signal = build_signal_from_ticker(
        {"status": "live", "last_price": 98.0, "open_price": 100.0},
        strategy_id=sell_id,
    )
    assert sell_signal["trailing_profit_lock_pct"] == 30.0


def test_momentum_breakout_respects_threshold_and_defaults_sells_to_futures():
    from app.strategy import configure_builtin_strategy

    configure_builtin_strategy("momentum_breakout", {"threshold_pct": 5})
    try:
        below_threshold = build_signal_from_ticker(
            {"status": "live", "last_price": 102.0, "open_price": 100.0},
            strategy_id="momentum_breakout",
        )
        assert below_threshold["action"] == "hold"

        sell_signal = build_signal_from_ticker(
            {"status": "live", "last_price": 94.0, "open_price": 100.0},
            strategy_id="momentum_breakout",
        )
        assert sell_signal["action"] == "sell"
        assert sell_signal["market"] == "futures"
    finally:
        configure_builtin_strategy("momentum_breakout", {"threshold_pct": 1})


def test_momentum_breakout_uses_safe_default_threshold_and_price_guard():
    configure_builtin_strategy("momentum_breakout", {"threshold_pct": 1})
    try:
        assert build_signal_from_ticker({"status": "live", "last_price": 100.2, "open_price": 100.0})["action"] == "hold"
        assert build_signal_from_ticker({"status": "live", "last_price": 100.0, "open_price": 0.0})["action"] == "hold"
    finally:
        configure_builtin_strategy("momentum_breakout", {"threshold_pct": 1})


def test_momentum_leverage_scales_with_higher_thresholds():
    configure_builtin_strategy("momentum_breakout", {"threshold_pct": 5})
    try:
        signal = build_signal_from_ticker({"status": "live", "last_price": 105.0, "open_price": 100.0})
        assert signal["action"] == "buy"
        assert signal["leverage"] == 1.0
    finally:
        configure_builtin_strategy("momentum_breakout", {"threshold_pct": 1})


def test_configured_spot_sell_remains_a_close_signal():
    configure_builtin_strategy("mean_reversion", {"market": "spot", "threshold_pct": 1})
    try:
        signal = build_signal_from_ticker(
            {"status": "live", "last_price": 102.0, "open_price": 100.0},
            strategy_id="mean_reversion",
        )
        assert signal["action"] == "sell"
        assert signal["market"] == "spot"
    finally:
        configure_builtin_strategy("mean_reversion", {})


@pytest.mark.parametrize(
    ("strategy_id", "ticker_values"),
    [
        ("momentum_breakout", [(105.0, 1.0), (107.0, 2.0), (114.0, 3.0)]),
        ("mean_reversion", [(101.0, 1.0), (101.4, 2.0), (102.8, 3.0)]),
        ("overnight_gap", [(101.0, 1.0), (101.4, 2.0), (102.8, 3.0)]),
    ],
)
def test_each_builtin_strategy_has_expected_leverage_tiers(strategy_id, ticker_values):
    configure_builtin_strategy(strategy_id, {"threshold_pct": 5 if strategy_id == "momentum_breakout" else 1})
    for last_price, expected_leverage in ticker_values:
        ticker = {"status": "live", "last_price": last_price, "open_price": 100.0}
        if strategy_id == "overnight_gap":
            ticker.update({"previous_close": 100.0, "session_open": last_price})
        signal = build_signal_from_ticker(ticker, strategy_id=strategy_id)
        assert signal["leverage"] == expected_leverage


def test_builtin_and_pairs_strategies_have_hold_cases():
    assert build_signal_from_ticker(
        {"status": "live", "last_price": 100.5, "open_price": 100.0},
        strategy_id="momentum_breakout",
    )["action"] == "hold"
    assert build_signal_from_ticker(
        {"status": "live", "last_price": 100.5, "open_price": 100.0},
        strategy_id="mean_reversion",
    )["action"] == "hold"
    assert build_signal_from_ticker(
        {"status": "live", "last_price": 100.0, "previous_close": 100.0, "session_open": 100.5},
        strategy_id="overnight_gap",
    )["action"] == "hold"
    pair = build_pairs_signal("AAPLUSDT", "TSLAUSDT", [100, 101, 100], [100, 100, 100], entry_zscore=2.0, exit_zscore=0.5)
    assert pair["action"] == "hold"


def test_pairs_signal_can_exit_and_config_does_not_apply_trade_values_to_hold():
    pair = build_pairs_signal("AAPLUSDT", "TSLAUSDT", [100, 110, 105], [100, 100, 100], entry_zscore=2.0, exit_zscore=0.5)
    assert pair["action"] == "exit_pair"
    configure_builtin_strategy("mean_reversion", {"position_size": 4, "leverage": 3, "threshold_pct": 1})
    signal = build_signal_from_ticker({"status": "live", "last_price": 100.5, "open_price": 100.0}, strategy_id="mean_reversion")
    assert signal["action"] == "hold"
    assert signal["size"] == 0.0
    assert signal["leverage"] == 1.0


def test_unregister_clears_active_and_symbol_mapping():
    strategy_id = "custom_unregister_state"
    register_custom_strategy(strategy_id, parse_structured_strategy({"action": "buy", "comparison": "open", "threshold_pct": 1}))
    configure_symbol_strategies({"AAPLUSDT": strategy_id})
    activate_strategy(strategy_id)
    assert strategy_module.unregister_custom_strategy(strategy_id) is True
    assert get_active_strategy_id() == "momentum_breakout"
    assert strategy_module.get_strategy_for_symbol("AAPLUSDT") == "momentum_breakout"


def test_strategy_config_rejects_leverage_and_stop_loss_above_bounds():
    with pytest.raises(ValueError, match="leverage"):
        configure_builtin_strategy("momentum_breakout", {"leverage": 4})
    with pytest.raises(ValueError, match="stop_loss"):
        configure_builtin_strategy("momentum_breakout", {"stop_loss_pct": 0})
    with pytest.raises(ValueError, match="leverage"):
        parse_structured_strategy({"action": "buy", "comparison": "open", "threshold_pct": 1, "leverage": 4})
    with pytest.raises(ValueError, match="stop_loss"):
        parse_structured_strategy({"action": "buy", "comparison": "open", "threshold_pct": 1, "stop_loss_pct": 0})


def test_activation_endpoint_rejects_unsafe_strategy_config():
    leverage_result = main.activate_strategy(
        "mean_reversion",
        main.StrategyActivationRequest(strategy_config={"leverage": 4}),
    )
    stop_loss_result = main.activate_strategy(
        "mean_reversion",
        main.StrategyActivationRequest(strategy_config={"stop_loss_pct": 0}),
    )

    assert leverage_result["status"] == "rejected"
    assert "leverage" in leverage_result["message"]
    assert stop_loss_result["status"] == "rejected"
    assert "stop_loss" in stop_loss_result["message"]


def test_parse_structured_strategy_rejects_invalid_market():
    with pytest.raises(ValueError, match="market"):
        parse_structured_strategy({
            "action": "buy",
            "comparison": "open",
            "threshold_pct": 1.5,
            "market": "options",
        })


def test_parse_structured_strategy_rejects_non_positive_threshold():
    with pytest.raises(ValueError, match="threshold"):
        parse_structured_strategy({
            "action": "buy",
            "comparison": "open",
            "threshold_pct": 0,
        })


def test_momentum_uses_percentage_for_sub_dollar_assets():
    from app.strategy import configure_builtin_strategy

    configure_builtin_strategy("momentum_breakout", {"threshold_pct": 10})
    try:
        signal = build_signal_from_ticker({"status": "live", "last_price": 0.55, "open_price": 0.50})
        assert signal["action"] == "buy"
    finally:
        configure_builtin_strategy("momentum_breakout", {"threshold_pct": 1})


def test_spot_buy_clamps_configured_leverage_to_one():
    strategy_id = "custom_spot_leverage_boundary"
    parsed = parse_structured_strategy({
        "action": "buy",
        "comparison": "open",
        "threshold_pct": 1,
        "market": "spot",
        "leverage": 3,
    })
    register_custom_strategy(strategy_id, parsed)
    signal = build_signal_from_ticker(
        {"status": "live", "last_price": 102.0, "open_price": 100.0},
        strategy_id=strategy_id,
    )
    assert signal["leverage"] == 1.0


def test_backtest_rejects_single_symbol_only_strategies():
    from app.strategy import backtest_strategy

    with pytest.raises(ValueError, match="not backtestable"):
        backtest_strategy("overnight_gap", [{"open": 100, "close": 101}])


def test_parse_natural_language_strategy_requires_explicit_threshold():
    with pytest.raises(ValueError, match="threshold"):
        parse_natural_language_strategy("mean reversion")


def test_parse_structured_strategy_rejects_invalid_comparison():
    with pytest.raises(ValueError, match="comparison"):
        parse_structured_strategy({
            "action": "buy",
            "comparison": "ema",
            "threshold_pct": 1.5,
        })


def test_parse_natural_language_strategy_supports_gemini_json(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    class DummyResponse:
        status_code = 200

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": "```json\n{\"kind\":\"builtin\",\"target_strategy\":\"mean_reversion\",\"threshold_pct\":1.0}\n```"
                                }
                            ]
                        }
                    }
                ]
            }

    def fake_post(url, headers, json, timeout):
        assert url == "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        assert headers["Content-Type"] == "application/json"
        assert headers["x-goog-api-key"] == "test-key"
        return DummyResponse()

    monkeypatch.setattr("app.strategy.requests.post", fake_post)

    parsed = parse_natural_language_strategy("fade moves at least 1% away from the opening price", use_gemini=True)

    assert parsed["kind"] == "builtin"
    assert parsed["target_strategy"] == "mean_reversion"
    assert parsed["threshold_pct"] == 1.0


def test_parse_strategy_endpoint_rejects_ambiguous_payloads():
    parsed = parse_strategy_endpoint({
        "text": "fade moves at least 1% away from the opening price",
        "strategy": {"action": "buy", "comparison": "open", "threshold_pct": 1.5},
    })

    assert parsed["status"] == "rejected"
    assert "either text or strategy" in parsed["message"]


def test_parse_strategy_endpoint_rejects_non_string_text():
    parsed = parse_strategy_endpoint({"text": 123})

    assert parsed["status"] == "rejected"
    assert "text must be a non-empty string" in parsed["message"]


def test_parse_strategy_endpoint_preserves_strategy_metadata_for_text_inputs():
    parsed = parse_strategy_endpoint({
        "text": "fade moves at least 1% away from the opening price",
        "name": "My Mean Reversion",
        "description": "Fade short-lived dislocations around the open.",
    })

    assert parsed["status"] == "parsed"
    assert parsed["name"] == "My Mean Reversion"
    assert parsed["description"] == "Fade short-lived dislocations around the open."
    assert parsed["strategy_id"] == "mean_reversion"


def test_strategy_catalog_exposes_prebuilt_strategy_definitions():
    assert set(STRATEGY_CATALOG) == {"momentum_breakout", "mean_reversion", "overnight_gap", "pairs_trading"}

    for strategy_id, definition in STRATEGY_CATALOG.items():
        assert definition["id"] == strategy_id
        assert definition["type"] == "prebuilt"
        assert definition["description"]


def test_builtin_strategies_adapt_leverage_to_signal_strength():
    activate_strategy("momentum_breakout")

    weak = build_signal_from_ticker({"status": "live", "last_price": 101.0, "open_price": 100.0})
    strong = build_signal_from_ticker({"status": "live", "last_price": 180.0, "open_price": 100.0})

    assert weak["leverage"] == 1.0
    assert strong["leverage"] == 3.0

    activate_strategy("mean_reversion")
    threshold_signal = build_signal_from_ticker({"status": "live", "last_price": 101.0, "open_price": 100.0})
    strong_reversion = build_signal_from_ticker({"status": "live", "last_price": 130.0, "open_price": 100.0})

    assert threshold_signal["leverage"] == 1.0
    assert strong_reversion["leverage"] == 3.0
    activate_strategy("momentum_breakout")


def test_symbol_strategy_mapping_selects_strategy_per_stock():
    configure_symbol_strategies({"AAPLUSDT": "momentum_breakout", "TSLAUSDT": "mean_reversion"})
    try:
        aapl = build_signal_from_ticker({"symbol": "AAPLUSDT", "status": "live", "last_price": 102.0, "open_price": 100.0})
        tsla = build_signal_from_ticker({"symbol": "TSLAUSDT", "status": "live", "last_price": 102.0, "open_price": 100.0})

        assert aapl["action"] == "buy"
        assert tsla["action"] == "sell"
    finally:
        configure_symbol_strategies({})


def test_strategy_activation_applies_selected_symbols(monkeypatch):
    monkeypatch.setattr(main.cycle_logger, "save_active_strategy", lambda strategy_id: {"status": "skipped"})
    main.agent_loop.configure_watched_symbols(["AAPLUSDT", "TSLAUSDT"])

    result = main.activate_strategy(
        "mean_reversion",
        main.StrategyActivationRequest(symbols=["tslausdt"]),
    )

    assert result["status"] == "activated"
    assert result["symbols"] == ["TSLAUSDT"]
    assert main.agent_loop.WATCHED_SYMBOLS == ["TSLAUSDT"]
    activate_strategy("momentum_breakout")


def test_strategy_activation_applies_builtin_risk_configuration(monkeypatch):
    configured = {}
    monkeypatch.setattr(main.cycle_logger, "save_active_strategy", lambda strategy_id: {"status": "skipped"})
    monkeypatch.setattr(
        main,
        "configure_builtin_strategy",
        lambda strategy_id, config: configured.update({"strategy_id": strategy_id, "config": config}),
    )

    result = main.activate_strategy(
        "mean_reversion",
        main.StrategyActivationRequest(
            strategy_config={"leverage": 2, "take_profit_pct": 4, "stop_loss_pct": 1},
        ),
    )

    assert result["status"] == "activated"
    assert configured == {
        "strategy_id": "mean_reversion",
        "config": {"leverage": 2, "take_profit_pct": 4, "stop_loss_pct": 1},
    }
    assert result["strategy_config"] == {"leverage": 2, "take_profit_pct": 4, "stop_loss_pct": 1}
    activate_strategy("momentum_breakout")


def test_strategy_catalog_uses_authenticated_runtime_active_strategy(monkeypatch):
    custom_id = "custom_buy_open_0_0_1"
    register_custom_strategy(
        custom_id,
        {
            "kind": "custom",
            "action": "buy",
            "comparison": "open",
            "threshold_pct": 0.1,
        },
        name="Charlie Bear",
    )

    class Runtime:
        strategy_id = custom_id

    monkeypatch.setattr(main, "restore_custom_strategies", lambda user_id: None)
    monkeypatch.setattr(main.user_runtime_registry, "get", lambda user_id: Runtime())

    catalog = main.strategies(main.AuthenticatedUser("user-1"))["strategies"]
    statuses = {strategy["id"]: strategy["status"] for strategy in catalog}

    assert statuses[custom_id] == "active"
    assert statuses["momentum_breakout"] == "inactive"


def test_strategy_activation_rejects_unsupported_symbols_without_mutation(monkeypatch):
    main.agent_loop.configure_watched_symbols(["AAPLUSDT"])
    activate_strategy("momentum_breakout")

    result = main.activate_strategy(
        "mean_reversion",
        main.StrategyActivationRequest(symbols=["MSFTUSDT"]),
    )

    assert result["status"] == "rejected"
    assert get_active_strategy_id() == "momentum_breakout"
    assert main.agent_loop.WATCHED_SYMBOLS == ["AAPLUSDT"]


def test_parse_strategy_endpoint_registers_structured_strategy_for_activation():
    parsed = parse_strategy_endpoint({
        "strategy": {
            "action": "buy",
            "comparison": "open",
            "threshold_pct": 1.5,
        }
    })

    assert parsed["status"] == "parsed"
    assert parsed["strategy_id"].startswith("custom_buy_open_")
    assert parsed["strategy_id"] in list_strategy_catalog()
    assert activate_strategy(parsed["strategy_id"]) is True
    assert get_active_strategy_id() == parsed["strategy_id"]

    ticker = {"status": "live", "last_price": 101.5, "open_price": 100.0}
    signal = build_signal_from_ticker(ticker)
    assert signal["action"] == "buy"


def test_parse_strategy_endpoint_preserves_custom_name_and_description():
    parsed = parse_strategy_endpoint({
        "name": "Opening Push",
        "description": "Buy strength above the opening price.",
        "strategy": {
            "action": "buy",
            "comparison": "open",
            "threshold_pct": 2.0,
        },
    })

    assert parsed["name"] == "Opening Push"
    assert parsed["description"] == "Buy strength above the opening price."
    assert list_strategy_catalog()[parsed["strategy_id"]]["name"] == "Opening Push"
