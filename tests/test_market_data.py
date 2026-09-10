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
