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


def test_parse_natural_language_strategy_supports_grok_json(monkeypatch):
    monkeypatch.setenv("GROK_API_KEY", "test-key")

    class DummyResponse:
        status_code = 200

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "```json\n{\"kind\":\"builtin\",\"target_strategy\":\"mean_reversion\",\"threshold_pct\":1.0}\n```"
                        }
                    }
                ]
            }

    def fake_post(url, headers, json, timeout):
        assert url.endswith("/chat/completions")
        assert headers["Authorization"] == "Bearer test-key"
        return DummyResponse()

    monkeypatch.setattr("app.strategy.requests.post", fake_post)

    parsed = parse_natural_language_strategy("fade moves at least 1% away from the opening price", use_grok=True)

    assert parsed["kind"] == "builtin"
    assert parsed["target_strategy"] == "mean_reversion"
    assert parsed["threshold_pct"] == 1.0


def test_parse_natural_language_strategy_prefers_grok_settings_over_stale_qwen_env(monkeypatch):
    monkeypatch.setenv("GROK_API_KEY", "test-key")
    monkeypatch.setenv("QWEN_MODEL", "qwen-plus-latest")
    monkeypatch.setenv("QWEN_API_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

    class DummyResponse:
        status_code = 200

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "```json\n{\"kind\":\"builtin\",\"target_strategy\":\"mean_reversion\",\"threshold_pct\":1.0}\n```"
                        }
                    }
                ]
            }

    def fake_post(url, headers, json, timeout):
        assert url == "https://api.x.ai/v1/chat/completions"
        assert json["model"] == "grok-2-latest"
        return DummyResponse()

    monkeypatch.setattr("app.strategy.requests.post", fake_post)

    parsed = parse_natural_language_strategy("fade moves at least 1% away from the opening price", use_grok=True)

    assert parsed["kind"] == "builtin"
    assert parsed["target_strategy"] == "mean_reversion"


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
