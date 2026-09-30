from __future__ import annotations

import inspect

from fastapi.testclient import TestClient

from app.auth import AuthenticatedUser, SupabaseAuth, UserCredentialVault
from app.main import app


def test_credential_vault_isolates_users(monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("PRIVA_CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    vault = UserCredentialVault()
    vault.put("user-a", {"api_key": "a", "api_secret": "secret-a", "passphrase": "pass-a"})
    vault.put("user-b", {"api_key": "b", "api_secret": "secret-b", "passphrase": "pass-b"})

    assert vault.get("user-a")["api_key"] == "a"
    assert vault.get("user-b")["api_key"] == "b"
    vault.delete("user-a")
    assert vault.get("user-a") is None
    assert vault.get("user-b")["api_key"] == "b"


def test_credential_vault_ignores_malformed_key_until_used(monkeypatch):
    monkeypatch.setenv("PRIVA_CREDENTIAL_ENCRYPTION_KEY", "not-a-fernet-key")

    vault = UserCredentialVault()

    assert vault.configured is False
    try:
        vault.put("user-a", {"api_key": "a", "api_secret": "secret", "passphrase": "pass"})
    except RuntimeError as exc:
        assert str(exc) == "PRIVA_CREDENTIAL_ENCRYPTION_KEY must be a valid Fernet key"
    else:
        raise AssertionError("malformed key should disable credential storage")


def test_supabase_auth_verifies_bearer_token(monkeypatch):
    auth = SupabaseAuth()
    auth.url = "https://example.supabase.co"
    auth.anon_key = "anon"

    class Response:
        status_code = 200

        def json(self):
            return {"id": "user-1", "email": "user@example.com"}

    class Session:
        def get(self, url, headers, timeout):
            assert url.endswith("/auth/v1/user")
            assert headers["Authorization"] == "Bearer token"
            return Response()

    auth.session = Session()
    user = auth.current_user("Bearer token")
    assert user == AuthenticatedUser("user-1", "user@example.com")


def test_auth_fails_closed_when_supabase_is_not_configured(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    auth = SupabaseAuth()
    try:
        auth.current_user("Bearer token")
    except HTTPException as exc:
        assert exc.status_code == 503
    else:
        raise AssertionError("missing Supabase configuration must fail closed")


def test_required_auth_rejects_missing_token(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    auth = SupabaseAuth()
    try:
        auth.current_user(None)
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 401
    else:
        raise AssertionError("missing token should be rejected when Supabase is configured")


def test_auth_rejects_invalid_token(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    auth = SupabaseAuth()
    try:
        auth.current_user("Bearer invalid-token")
    except HTTPException as exc:
        assert exc.status_code == 401
    else:
        raise AssertionError("invalid token must be rejected")


def test_risk_settings_endpoints_require_auth(monkeypatch):
    from app.auth import supabase_auth

    monkeypatch.setattr(supabase_auth, "url", "https://example.supabase.co")
    monkeypatch.setattr(supabase_auth, "anon_key", "anon")
    monkeypatch.setattr(supabase_auth, "user_from_token", lambda token: None)

    client = TestClient(app)

    response = client.get("/risk-settings")
    assert response.status_code == 401

    response = client.post("/risk-settings", json={"max_position_size": 1000})
    assert response.status_code == 401


def test_legacy_agent_and_risk_endpoints_require_auth(monkeypatch):
    from app.auth import supabase_auth

    monkeypatch.setattr(supabase_auth, "url", "https://example.supabase.co")
    monkeypatch.setattr(supabase_auth, "anon_key", "anon")
    monkeypatch.setattr(supabase_auth, "user_from_token", lambda token: None)
    client = TestClient(app)

    assert client.get("/agent-cycle").status_code == 401
    assert client.get("/agent-settings").status_code == 401
    assert client.get("/kill-switch").status_code == 401
    assert client.post("/intent/evaluate", json={"symbol": "AAPLUSDT", "side": "buy", "qty": 1, "entry_price": 1}).status_code == 401
    assert client.post("/risk-check", json={"trade": {}}).status_code == 401


def test_every_protected_route_rejects_invalid_auth(monkeypatch):
    from app.auth import supabase_auth

    monkeypatch.setattr(supabase_auth, "url", "https://example.supabase.co")
    monkeypatch.setattr(supabase_auth, "anon_key", "anon")
    monkeypatch.setattr(supabase_auth, "user_from_token", lambda token: None)
    client = TestClient(app)
    protected_requests = [
        ("GET", "/agent-cycle", None),
        ("GET", "/agent-loop", None),
        ("GET", "/agent-settings", None),
        ("POST", "/agent-settings", {"market": "futures"}),
        ("GET", "/account/balance", None),
        ("GET", "/account/balance-history", None),
        ("GET", "/user/agent-loop", None),
        ("GET", "/user/agent-settings", None),
        ("POST", "/user/market-settings", {"market": "futures"}),
        ("POST", "/user/execution-settings", {"markets": ["futures"], "modes": ["autonomous"]}),
        ("POST", "/user/agent-settings", {}),
        ("GET", "/account/status", None),
        ("POST", "/account/connect", {"api_key": "a", "api_secret": "b", "passphrase": "c"}),
        ("DELETE", "/account/disconnect", None),
        ("POST", "/user/backfill-trades", {"start_time": 1, "end_time": 2}),
        ("GET", "/auth/session", None),
        ("GET", "/status", None),
        ("GET", "/positions", None),
        ("POST", "/positions/AAPLUSDT/close", {"position_side": "buy"}),
        ("POST", "/user/reset-trading-session", {"confirm": True}),
        ("GET", "/pnl", None),
        ("GET", "/risk-usage", None),
        ("GET", "/risk-settings", None),
        ("POST", "/risk-settings", {"max_position_size": 1000}),
        ("GET", "/activity-log", None),
        ("GET", "/strategies", None),
        ("POST", "/strategies/mean_reversion/activate", {}),
        ("DELETE", "/strategies/custom_one", None),
        ("POST", "/strategies/mean_reversion/backtest", {}),
        ("POST", "/strategies/parse", {"text": "simple strategy"}),
        ("GET", "/kill-switch", None),
        ("POST", "/kill-switch", {"enabled": False}),
        ("POST", "/intent/evaluate", {"symbol": "AAPLUSDT", "side": "buy", "qty": 1, "entry_price": 1}),
        ("GET", "/risk-view", None),
        ("POST", "/risk-check", {"trade": {}}),
        ("POST", "/paper-trade", {"symbol": "AAPLUSDT", "side": "buy", "qty": 1, "entry_price": 1}),
    ]

    for method, path, body in protected_requests:
        response = client.request(method, path, json=body, headers={"Authorization": "Bearer invalid"})
        assert response.status_code == 401, f"{method} {path} returned {response.status_code}"


def test_legacy_connection_routes_are_removed():
    client = TestClient(app)
    assert client.post("/connection/bitget", json={}).status_code == 404
    assert client.post("/connection/bitget/disconnect", json={}).status_code == 404


def test_app_lifespan_refuses_to_start_without_supabase(monkeypatch):
    import asyncio
    from app import main
    from app.auth import supabase_auth

    monkeypatch.setattr(supabase_auth, "url", "")
    monkeypatch.setattr(supabase_auth, "anon_key", "")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    async def start_app():
        async with main.lifespan(main.app):
            pass

    try:
        asyncio.run(start_app())
    except RuntimeError as exc:
        assert "SUPABASE_URL" in str(exc)
    else:
        raise AssertionError("backend startup must fail without Supabase configuration")


def test_disconnected_users_cannot_access_balance_agent_or_trade(monkeypatch):
    from app.auth import supabase_auth
    from app.paper_execution import BitgetPaperExecutionClient

    monkeypatch.setattr(supabase_auth, "url", "https://example.supabase.co")
    monkeypatch.setattr(supabase_auth, "anon_key", "anon")
    monkeypatch.setattr(supabase_auth, "user_from_token", lambda token: AuthenticatedUser("new-user"))
    monkeypatch.setattr("app.main.execution_client_for", lambda user: BitgetPaperExecutionClient())
    client = TestClient(app)

    assert client.get("/account/balance", headers={"Authorization": "Bearer valid"}).status_code == 409
    assert client.get("/agent-cycle", headers={"Authorization": "Bearer valid"}).status_code == 409
    assert client.post(
        "/paper-trade",
        json={"symbol": "AAPLUSDT", "side": "buy", "qty": 1, "entry_price": 1},
        headers={"Authorization": "Bearer valid"},
    ).status_code == 409


def test_user_agent_loop_starts_runtime_on_running_event_loop(monkeypatch):
    import asyncio
    from app import main

    started = []

    def start_runtime(user_id, client):
        asyncio.get_running_loop()
        started.append(user_id)

    monkeypatch.setitem(
        app.dependency_overrides,
        main.current_user,
        lambda: AuthenticatedUser("user-1"),
    )
    monkeypatch.setattr(main, "require_connected_client", lambda user: object())
    monkeypatch.setattr(main.user_runtime_registry, "get", lambda user_id: None)
    monkeypatch.setattr(main.user_runtime_registry, "start", start_runtime)
    monkeypatch.setattr(main.user_runtime_registry, "status", lambda user_id: {"running": True})

    response = TestClient(app).get("/user/agent-loop")

    assert response.status_code == 200
    assert response.json() == {"running": True}
    assert started == ["user-1"]


def test_risk_requests_reject_client_supplied_user_id():
    from pydantic import ValidationError
    from app.main import IntentEvaluationRequest, RiskCheckRequest

    intent_payload = {
        "symbol": "AAPLUSDT",
        "side": "buy",
        "qty": 1,
        "entry_price": 1,
        "user_id": "user-b",
    }
    risk_payload = {"trade": {}, "user_id": "user-b"}

    for model, payload in ((IntentEvaluationRequest, intent_payload), (RiskCheckRequest, risk_payload)):
        try:
            model(**payload)
        except ValidationError:
            continue
        raise AssertionError("request-supplied user_id must be rejected")


def test_user_risk_engines_are_isolated_by_user():
    from app import main

    engine_a = main._risk_engine_for_user("user-a")
    engine_a.update_settings({"max_position_size": 1500, "max_daily_loss": 500})

    engine_b = main._risk_engine_for_user("user-b")
    assert engine_a.max_position_size == 1500
    assert engine_b.max_position_size == main.DEFAULT_RISK_SETTINGS["max_position_size"]
    assert engine_b.max_daily_loss == main.DEFAULT_RISK_SETTINGS["max_daily_loss"]


def test_user_risk_settings_allowlist_strips_supabase_metadata():
    from app import main

    sanitized = main._normalize_user_risk_settings({
        "user_id": "user-a",
        "max_position_size": 1200,
        "max_daily_loss": 600,
        "max_leverage": 7,
        "enabled": True,
        "allowed_symbols": ["AAPLUSDT"],
        "created_at": "2026-09-27T00:00:00Z",
    })

    assert sanitized == {
        "max_position_size": 1200,
        "max_daily_loss": 600,
        "max_leverage": 7,
        "enabled": True,
        "allowed_symbols": ["AAPLUSDT"],
    }

    engine = main._risk_engine_for_user("user-a", settings=sanitized)
    assert engine.max_position_size == 1200
    assert engine.max_daily_loss == 600
    assert engine.enabled is True


def test_risk_engine_kwargs_are_strictly_derived_from_constructor_signature():
    from app import main
    from app.risk_engine import RiskEngine

    row = {
        "user_id": "user-a",
        "market": "futures",
        "take_profit_pct": 5,
        "stop_loss_pct": 2,
        "close_on_signal_violation": True,
        "execution_profiles": ["autonomous:futures"],
        "enabled": False,
        "updated_at": "2026-09-27T00:00:00Z",
        "strategy_id": "mean_reversion",
        "strategy_config": {"threshold_pct": 2},
        "symbols": ["AAPLUSDT", "TSLAUSDT"],
        "strategy_by_symbol": {"AAPLUSDT": "mean_reversion"},
        "max_position_size": 9001,
        "max_daily_loss": 321,
        "max_leverage": 4,
        "risk_enabled": True,
        "allowed_symbols": ["AAPLUSDT", "TSLAUSDT"],
        "pnl_reset_at": None,
    }

    resolved = main._normalize_user_risk_settings(row)
    assert set(resolved) <= set(inspect.signature(RiskEngine.__init__).parameters) - {"self"}
    assert "risk_enabled" not in resolved
    RiskEngine(**resolved)


def test_builtin_strategy_configs_are_isolated_by_user():
    from app import strategy as strategy_module

    strategy_module.configure_builtin_strategy("momentum_breakout", {"threshold_pct": 3.0}, user_id="user-a")
    strategy_module.configure_builtin_strategy("momentum_breakout", {"threshold_pct": 7.0}, user_id="user-b")

    assert strategy_module._get_builtin_strategy_config("momentum_breakout", user_id="user-a")["threshold_pct"] == 3.0
    assert strategy_module._get_builtin_strategy_config("momentum_breakout", user_id="user-b")["threshold_pct"] == 7.0

    signal_a = strategy_module.build_signal_from_ticker(
        {"status": "live", "last_price": 104.0, "open_price": 100.0},
        strategy_id="momentum_breakout",
        user_id="user-a",
    )
    signal_b = strategy_module.build_signal_from_ticker(
        {"status": "live", "last_price": 104.0, "open_price": 100.0},
        strategy_id="momentum_breakout",
        user_id="user-b",
    )
    assert signal_a["action"] == "buy"
    assert signal_b["action"] == "hold"
