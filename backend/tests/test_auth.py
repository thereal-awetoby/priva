from __future__ import annotations

from app.auth import AuthenticatedUser, SupabaseAuth, UserCredentialVault


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


def test_required_auth_rejects_missing_token():
    auth = SupabaseAuth()
    auth.required = True
    try:
        auth.current_user(None)
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 401
    else:
        raise AssertionError("missing token should be rejected")
