import json

from app.paper_execution import BitgetPaperExecutionClient


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse({"code": "00000", "data": {"orderId": "paper-123"}})


def test_paper_client_fails_closed_without_credentials(monkeypatch):
    for key in ("BITGET_API_KEY", "BITGET_API_SECRET", "BITGET_API_PASSPHRASE"):
        monkeypatch.delenv(key, raising=False)

    session = FakeSession()
    client = BitgetPaperExecutionClient(session=session)

    result = client.place_market_order({"symbol": "AAPLUSDT", "side": "buy", "qty": 5})

    assert result["status"] == "not_configured"
    assert session.calls == []


def test_paper_client_submits_paper_order(monkeypatch):
    monkeypatch.setenv("BITGET_API_KEY", "key")
    monkeypatch.setenv("BITGET_API_SECRET", "secret")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "passphrase")

    session = FakeSession()
    client = BitgetPaperExecutionClient(session=session)
    result = client.place_market_order(
        {"symbol": "AAPLUSDT", "side": "buy", "qty": 5}
    )

    url, kwargs = session.calls[0]
    body = json.loads(kwargs["data"])
    assert result == {"status": "submitted", "exchange": {"code": "00000", "data": {"orderId": "paper-123"}}, "order_id": "paper-123"}
    assert url.endswith("/api/v2/mix/order/place-order")
    assert kwargs["headers"]["paptrading"] == "1"
    assert body["productType"] == "USDT-FUTURES"
    assert body["symbol"] == "AAPLUSDT"


def test_paper_client_submits_spot_order(monkeypatch):
    monkeypatch.setenv("BITGET_API_KEY", "key")
    monkeypatch.setenv("BITGET_API_SECRET", "secret")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "passphrase")

    session = FakeSession()
    client = BitgetPaperExecutionClient(session=session)
    client.place_market_order(
        {
            "symbol": "BTCUSDT",
            "side": "buy",
            "qty": 0.01,
            "entry_price": 100000,
            "market": "spot",
        }
    )

    url, kwargs = session.calls[0]
    body = json.loads(kwargs["data"])
    assert url.endswith("/api/v2/spot/trade/place-order")
    assert kwargs["headers"]["paptrading"] == "1"
    assert body["symbol"] == "BTCUSDT"
    assert body["size"] == "1000.0"
    assert "productType" not in body
