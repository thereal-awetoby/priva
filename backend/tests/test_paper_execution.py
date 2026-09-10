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

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = FakeResponse({"code": "00000", "data": [{"symbol": "AAPLUSDT", "total": "1"}]})
        return response


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
    assert result == {
        "status": "submitted",
        "trade_side": "open",
        "side": "buy",
        "qty": 5.0,
        "entry_price": 0.0,
        "exchange": {"code": "00000", "data": {"orderId": "paper-123"}},
        "order_id": "paper-123",
    }
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


def test_paper_client_submits_close_order(monkeypatch):
    monkeypatch.setenv("BITGET_API_KEY", "key")
    monkeypatch.setenv("BITGET_API_SECRET", "secret")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "passphrase")
    monkeypatch.setenv("BITGET_POSITION_MODE", "hedge")

    session = FakeSession()
    client = BitgetPaperExecutionClient(session=session)
    client.place_market_order(
        {
            "symbol": "AAPLUSDT",
            "side": "sell",
            "qty": 1,
            "entry_price": 325,
            "market": "futures",
            "reduce_only": True,
            "position_side": "buy",
        }
    )

    _, kwargs = session.calls[0]
    body = json.loads(kwargs["data"])
    assert body["tradeSide"] == "close"
    assert body["side"] == "sell"
    assert body["posSide"] == "long"
    assert body["marginMode"] == "isolated"


def test_paper_client_uses_position_margin_mode_on_close(monkeypatch):
    monkeypatch.setenv("BITGET_API_KEY", "key")
    monkeypatch.setenv("BITGET_API_SECRET", "secret")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "passphrase")
    monkeypatch.setenv("BITGET_POSITION_MODE", "hedge")

    session = FakeSession()
    client = BitgetPaperExecutionClient(session=session)
    client.place_market_order(
        {
            "symbol": "AAPLUSDT",
            "side": "sell",
            "qty": 1,
            "entry_price": 325,
            "market": "futures",
            "reduce_only": True,
            "position_side": "buy",
            "margin_mode": "crossed",
        }
    )

    body = json.loads(session.calls[0][1]["data"])
    assert body["marginMode"] == "crossed"


def test_paper_client_submits_one_way_reduce_only_close(monkeypatch):
    monkeypatch.setenv("BITGET_API_KEY", "key")
    monkeypatch.setenv("BITGET_API_SECRET", "secret")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "passphrase")
    monkeypatch.delenv("BITGET_POSITION_MODE", raising=False)

    session = FakeSession()
    client = BitgetPaperExecutionClient(session=session)
    client.place_market_order(
        {
            "symbol": "AAPLUSDT",
            "side": "sell",
            "qty": 1,
            "market": "futures",
            "reduce_only": True,
        }
    )

    body = json.loads(session.calls[0][1]["data"])
    assert body["reduceOnly"] == "YES"
    assert body["side"] == "sell"
    assert "tradeSide" not in body
    assert "holdSide" not in body


def test_paper_client_submits_hedge_mode_open_order(monkeypatch):
    monkeypatch.setenv("BITGET_API_KEY", "key")
    monkeypatch.setenv("BITGET_API_SECRET", "secret")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "passphrase")
    monkeypatch.setenv("BITGET_POSITION_MODE", "hedge")

    session = FakeSession()
    client = BitgetPaperExecutionClient(session=session)
    client.place_market_order(
        {"symbol": "AAPLUSDT", "side": "buy", "qty": 1, "market": "futures"}
    )

    body = json.loads(session.calls[0][1]["data"])
    assert body["tradeSide"] == "open"
    assert body["posSide"] == "long"


def test_paper_client_infers_pos_side_for_reduce_only_close(monkeypatch):
    monkeypatch.setenv("BITGET_API_KEY", "key")
    monkeypatch.setenv("BITGET_API_SECRET", "secret")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "passphrase")
    monkeypatch.setenv("BITGET_POSITION_MODE", "hedge")

    session = FakeSession()
    client = BitgetPaperExecutionClient(session=session)
    client.place_market_order(
        {"symbol": "AAPLUSDT", "side": "sell", "qty": 1, "market": "futures", "reduce_only": True}
    )

    body = json.loads(session.calls[0][1]["data"])
    assert body["tradeSide"] == "close"
    assert body["posSide"] == "long"


def test_paper_client_accepts_long_short_position_aliases(monkeypatch):
    monkeypatch.setenv("BITGET_API_KEY", "key")
    monkeypatch.setenv("BITGET_API_SECRET", "secret")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "passphrase")
    monkeypatch.setenv("BITGET_POSITION_MODE", "hedge")

    session = FakeSession()
    client = BitgetPaperExecutionClient(session=session)
    client.place_market_order(
        {"symbol": "AAPLUSDT", "side": "sell", "qty": 1, "market": "futures", "trade_side": "close", "position_side": "long"}
    )

    body = json.loads(session.calls[0][1]["data"])
    assert body["tradeSide"] == "close"
    assert body["posSide"] == "long"


def test_paper_client_reads_futures_positions(monkeypatch):
    monkeypatch.setenv("BITGET_API_KEY", "key")
    monkeypatch.setenv("BITGET_API_SECRET", "secret")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "passphrase")

    session = FakeSession()
    result = BitgetPaperExecutionClient(session=session).fetch_futures_positions()

    url, kwargs = session.calls[0]
    assert result["status"] == "ok"
    assert result["positions"][0]["symbol"] == "AAPLUSDT"
    assert url.endswith("/api/v2/mix/position/all-position?marginCoin=USDT&productType=USDT-FUTURES")
    assert kwargs["headers"]["paptrading"] == "1"


def test_paper_client_reads_sanitized_account_mode(monkeypatch):
    monkeypatch.setenv("BITGET_API_KEY", "key")
    monkeypatch.setenv("BITGET_API_SECRET", "secret")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "passphrase")

    class AccountSession(FakeSession):
        def get(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return FakeResponse({"code": "00000", "data": {"posMode": "one_way_mode", "available": "999"}})

    session = AccountSession()
    result = BitgetPaperExecutionClient(session=session).fetch_account_mode()

    assert result == {
        "status": "ok",
        "symbol": "AAPLUSDT",
        "product_type": "USDT-FUTURES",
        "position_mode": "one_way",
    }
    assert "available" not in result


def test_paper_client_normalizes_hedge_mode_aliases(monkeypatch):
    monkeypatch.setenv("BITGET_API_KEY", "key")
    monkeypatch.setenv("BITGET_API_SECRET", "secret")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "passphrase")
    monkeypatch.setenv("BITGET_POSITION_MODE", "hedge_mode")

    session = FakeSession()
    client = BitgetPaperExecutionClient(session=session)
    client.place_market_order({"symbol": "AAPLUSDT", "side": "buy", "qty": 1, "market": "futures"})

    body = json.loads(session.calls[0][1]["data"])
    assert body["tradeSide"] == "open"
    assert body["posSide"] == "long"
