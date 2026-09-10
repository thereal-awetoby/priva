from app.supabase_logging import SupabaseCycleLogger


class FakeResponse:
    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse()


def test_supabase_logger_skips_when_unconfigured(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    session = FakeSession()

    result = SupabaseCycleLogger(session=session).log_cycle({"symbol": "AAPLUSDT"})

    assert result["status"] == "not_configured"
    assert session.calls == []


def test_supabase_logger_inserts_cycle(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    session = FakeSession()

    result = SupabaseCycleLogger(session=session).log_cycle(
        {
            "symbol": "AAPLUSDT",
            "status": "submitted",
            "decision": {"action": "buy"},
            "risk_check": {"allowed": True},
            "intent": {"intent_hash": "abc"},
            "order": {"order_id": "order-1"},
        }
    )

    url, kwargs = session.calls[0]
    assert result["status"] == "logged"
    assert url == "https://example.supabase.co/rest/v1/agent_cycles"
    assert kwargs["headers"]["Authorization"] == "Bearer secret"
    assert kwargs["json"]["symbol"] == "AAPLUSDT"
    assert kwargs["json"]["order_result"]["order_id"] == "order-1"
