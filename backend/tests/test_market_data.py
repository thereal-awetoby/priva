from app.market_data import BitgetMarketDataService


def test_normalize_ticker_payload():
    service = BitgetMarketDataService()
    payload = {
        "symbol": "AAPLUSDT",
        "last": "223.12",
        "open": "220.00",
        "high": "225.50",
        "low": "219.10",
        "baseVolume": "953200",
        "quoteVolume": "212350000",
        "ts": 1726000000000,
    }

    normalized = service.normalize_ticker_payload(payload)

    assert normalized["symbol"] == "AAPLUSDT"
    assert normalized["last_price"] == 223.12
    assert normalized["high_24h"] == 225.5
    assert normalized["status"] == "live"


def test_fallback_when_api_error():
    service = BitgetMarketDataService()
    fallback = service.build_fallback_ticker("NVDAUSDT", "network-unavailable")

    assert fallback["symbol"] == "NVDAUSDT"
    assert fallback["status"] == "fallback"
    assert fallback["source"] == "bitget_public"


def test_normalize_ticker_list_response():
    service = BitgetMarketDataService()
    payload = {
        "code": "00000",
        "data": [
            {"symbol": "BTCUSDT", "last": "100", "open": "90", "ts": "1726000000000"},
            {"symbol": "ETHUSDT", "last": "200", "open": "190", "ts": "1726000000000"},
        ],
    }

    data = payload["data"]
    selected = next(item for item in data if item["symbol"] == "ETHUSDT")
    normalized = service.normalize_ticker_payload(selected)

    assert normalized["symbol"] == "ETHUSDT"
    assert normalized["last_price"] == 200.0


def test_normalize_futures_ticker_payload():
    service = BitgetMarketDataService()
    normalized = service.normalize_ticker_payload(
        {
            "symbol": "AAPLUSDT",
            "lastPr": "223.12",
            "open24h": "220.00",
            "high24h": "225.50",
            "low24h": "219.10",
            "usdtVolume": "212350000",
            "ts": "1726000000000",
        }
    )

    assert normalized["symbol"] == "AAPLUSDT"
    assert normalized["last_price"] == 223.12
    assert normalized["open_price"] == 220.0


def test_fetch_daily_gap_context(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "code": "00000",
                "data": [
                    ["1726000000000", "100", "101", "99", "100.5", "0", "0"],
                    ["1726086400000", "103", "104", "102", "103.5", "0", "0"],
                ],
            }

    monkeypatch.setattr("app.market_data.requests.get", lambda *args, **kwargs: Response())
    context = BitgetMarketDataService().fetch_daily_gap_context("AAPLUSDT")

    assert context["status"] == "live"
    assert context["previous_close"] == 100.5
    assert context["session_open"] == 103.0


def test_fetch_pair_daily_closes(monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            symbol = calls[-1]
            base = 100 if symbol == "AAPLUSDT" else 200
            return {"code": "00000", "data": [["1", str(base), "0", "0", str(base + 1), "0", "0"], ["2", str(base + 1), "0", "0", str(base + 2), "0", "0"]]}

    def fake_get(url, params, **kwargs):
        calls.append(params["symbol"])
        return Response()

    monkeypatch.setattr("app.market_data.requests.get", fake_get)
    result = BitgetMarketDataService().fetch_pair_daily_closes("AAPLUSDT", "TSLAUSDT")

    assert result["status"] == "live"
    assert result["first"]["closes"] == [101.0, 102.0]
    assert result["second"]["closes"] == [201.0, 202.0]


def test_fetch_spot_ticker_maps_logical_symbol_to_exchange_symbol(monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"code": "00000", "data": [{"symbol": "RAAPLUSDT", "last": "201", "open": "200", "ts": "1726000000000"}]}

    def fake_get(url, params, **kwargs):
        calls.append(params)
        return Response()

    monkeypatch.setattr("app.market_data.requests.get", fake_get)
    result = BitgetMarketDataService().fetch_spot_ticker("AAPLUSDT")

    assert calls[0] == {"category": "SPOT"}
    assert result["symbol"] == "AAPLUSDT"
    assert result["last_price"] == 201.0
