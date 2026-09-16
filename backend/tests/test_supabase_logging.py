from app.supabase_logging import SupabaseCycleLogger


class FakeResponse:
    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, payload=None):
        self.calls = []
        self.payload = payload or []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse()

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = FakeResponse()
        response.json = lambda: self.payload
        return response


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
    assert kwargs["json"]["session_id"]


def test_supabase_logger_reads_cycles(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    session = FakeSession([{"symbol": "AAPLUSDT", "status": "submitted"}])

    cycles = SupabaseCycleLogger(session=session).fetch_cycles(limit=10)

    assert cycles == [{"symbol": "AAPLUSDT", "status": "submitted"}]
    assert session.calls[0][1]["params"]["limit"] == 10


def test_supabase_logger_filters_cycles_by_session(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    session = FakeSession([])

    SupabaseCycleLogger(session=session).fetch_cycles(session_id="session-1")

    assert session.calls[0][1]["params"]["session_id"] == "eq.session-1"


def test_supabase_logger_detects_open_position(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    session = FakeSession([{"id": 1}])

    assert SupabaseCycleLogger(session=session).has_open_position("AAPLUSDT") is True
    assert session.calls[0][1]["params"]["symbol"] == "eq.AAPLUSDT"


def test_supabase_logger_reads_active_strategy(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    session = FakeSession([{"strategy_id": "mean_reversion"}])

    strategy_id = SupabaseCycleLogger(session=session).fetch_active_strategy()

    assert strategy_id == "mean_reversion"
    assert session.calls[0][1]["params"]["id"] == "eq.global"


def test_supabase_logger_saves_active_strategy(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    session = FakeSession()

    result = SupabaseCycleLogger(session=session).save_active_strategy("mean_reversion")

    url, kwargs = session.calls[0]
    assert result["status"] == "saved"
    assert url.endswith("/rest/v1/strategy_settings")
    assert kwargs["json"] == {"id": "global", "strategy_id": "mean_reversion"}


def test_supabase_logger_saves_custom_strategy(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    session = FakeSession()

    result = SupabaseCycleLogger(session=session).save_custom_strategy(
        "user-1",
        "custom_opening_push",
        {"kind": "custom", "action": "buy", "comparison": "open"},
        "Opening Push",
        "Buy strength above the opening price.",
    )

    url, kwargs = session.calls[0]
    assert result["status"] == "saved"
    assert url.endswith("/rest/v1/custom_strategies")
    assert kwargs["params"]["on_conflict"] == "user_id,strategy_id"
    assert kwargs["json"]["user_id"] == "user-1"
    assert kwargs["json"]["name"] == "Opening Push"
    assert kwargs["json"]["definition"]["action"] == "buy"


def test_supabase_logger_reads_custom_strategies(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    session = FakeSession([{"strategy_id": "custom_opening_push", "definition": {}}])

    strategies = SupabaseCycleLogger(session=session).fetch_custom_strategies("user-1")

    assert strategies[0]["strategy_id"] == "custom_opening_push"
    assert session.calls[0][1]["params"]["user_id"] == "eq.user-1"
