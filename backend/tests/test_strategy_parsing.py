from app.main import parse_strategy as parse_strategy_endpoint
from app import main
from app.strategy import STRATEGY_CATALOG, build_signal_from_ticker, configure_symbol_strategies, get_active_strategy_id, list_strategy_catalog, parse_natural_language_strategy, parse_structured_strategy, register_custom_strategy, activate_strategy

import pytest


def test_parse_natural_language_strategy_supports_mean_reversion_text():
    parsed = parse_natural_language_strategy("fade moves at least 1% away from the opening price")

    assert parsed["kind"] == "builtin"
    assert parsed["target_strategy"] == "mean_reversion"
    assert parsed["threshold_pct"] == 1.0


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


def test_parse_structured_strategy_rejects_invalid_market():
    with pytest.raises(ValueError, match="market"):
        parse_structured_strategy({
            "action": "buy",
            "comparison": "open",
            "threshold_pct": 1.5,
            "market": "options",
        })


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
        assert url == "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=test-key"
        assert headers["Content-Type"] == "application/json"
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
    assert set(STRATEGY_CATALOG) == {"momentum_breakout", "mean_reversion"}

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
