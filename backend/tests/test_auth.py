from __future__ import annotations

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


def test_optional_auth_falls_back_to_local_dev_for_invalid_token(monkeypatch):
    monkeypatch.setenv("PRIVA_AUTH_REQUIRED", "false")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)

    auth = SupabaseAuth()
    user = auth.current_user("Bearer invalid-token")
    assert user == AuthenticatedUser("local-development")


def test_required_auth_rejects_missing_token(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    monkeypatch.setenv("PRIVA_AUTH_REQUIRED", "true")

    auth = SupabaseAuth()
    auth.required = True
    try:
        auth.current_user(None)
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 401
    else:
        raise AssertionError("missing token should be rejected when Supabase is configured")


def test_required_flag_does_not_force_auth_without_supabase_config(monkeypatch):
    monkeypatch.setenv("PRIVA_AUTH_REQUIRED", "true")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)

    auth = SupabaseAuth()

    assert auth.required is True
    assert auth.current_user(None) == AuthenticatedUser("local-development")


def test_risk_settings_endpoints_require_auth(monkeypatch):
    from app.auth import supabase_auth

    monkeypatch.setattr(supabase_auth, "required", True)
    monkeypatch.setattr(supabase_auth, "url", "https://example.supabase.co")
    monkeypatch.setattr(supabase_auth, "anon_key", "anon")
    monkeypatch.setattr(supabase_auth, "user_from_token", lambda token: None)

    client = TestClient(app)

    response = client.get("/risk-settings")
    assert response.status_code == 401

    response = client.post("/risk-settings", json={"max_position_size": 1000})
    assert response.status_code == 401


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


def test_builtin_strategy_configs_are_isolated_by_user():
    from app import strategy as strategy_module

    strategy_module.configure_builtin_strategy("momentum_breakout", {"threshold_pct": 3.0}, user_id="user-a")
    strategy_module.configure_builtin_strategy("momentum_breakout", {"threshold_pct": 7.0}, user_id="user-b")

    assert strategy_module._get_builtin_strategy_config("momentum_breakout", user_id="user-a")["threshold_pct"] == 3.0
    assert strategy_module._get_builtin_strategy_config("momentum_breakout", user_id="user-b")["threshold_pct"] == 7.0
