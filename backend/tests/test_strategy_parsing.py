from app.main import parse_strategy as parse_strategy_endpoint
from app.strategy import parse_natural_language_strategy, parse_structured_strategy

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
