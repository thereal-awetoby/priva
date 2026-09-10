from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)


class BitgetMarketDataService:
    """Fetch public ticker data from Bitget and normalize it for Priva."""

    BASE_URL = "https://api.bitget.com/api/v2"

    def __init__(self) -> None:
        self.last_snapshot: dict[str, Any] | None = None

    def fetch_spot_ticker(self, symbol: str) -> dict[str, Any]:
        url = f"{self.BASE_URL}/spot/market/ticker"
        params = {"symbol": symbol}

        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            payload = response.json()

            if payload.get("code") not in (None, "00000", 0, "0"):
                fallback = self.build_fallback_ticker(symbol, payload.get("msg", "bitget_error"))
                self.last_snapshot = fallback
                return fallback

            data = payload.get("data") or {}
            if not data:
                fallback = self.build_fallback_ticker(symbol, "empty_data")
                self.last_snapshot = fallback
                return fallback

            normalized = self.normalize_ticker_payload(data)
            self.last_snapshot = normalized
            return normalized
        except requests.RequestException as exc:
            logger.warning("Bitget public market fetch failed for %s: %s", symbol, exc)
            fallback = self.build_fallback_ticker(symbol, str(exc))
            self.last_snapshot = fallback
            return fallback

    def get_market_snapshot(self, symbol: str) -> dict[str, Any]:
        ticker = self.fetch_spot_ticker(symbol)
        return {
            "symbol": symbol.upper(),
            "data": ticker,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "status": ticker.get("status", "unknown"),
        }

    def normalize_ticker_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        symbol = str(payload.get("symbol", "UNKNOWN")).upper()
        last_price = float(payload.get("last", 0) or 0)
        open_price = float(payload.get("open", 0) or 0)
        high_24h = float(payload.get("high", 0) or 0)
        low_24h = float(payload.get("low", 0) or 0)
        base_volume = float(payload.get("baseVolume", 0) or 0)
        quote_volume = float(payload.get("quoteVolume", 0) or 0)
        timestamp_ms = int(payload.get("ts", 0) or 0)

        return {
            "symbol": symbol,
            "last_price": last_price,
            "open_price": open_price,
            "high_24h": high_24h,
            "low_24h": low_24h,
            "base_volume": base_volume,
            "quote_volume": quote_volume,
            "timestamp_ms": timestamp_ms,
            "timestamp_iso": datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).isoformat(),
            "status": "live",
            "source": "bitget_public",
        }

    def build_fallback_ticker(self, symbol: str, reason: str) -> dict[str, Any]:
        return {
            "symbol": str(symbol).upper(),
            "last_price": 0.0,
            "open_price": 0.0,
            "high_24h": 0.0,
            "low_24h": 0.0,
            "base_volume": 0.0,
            "quote_volume": 0.0,
            "timestamp_ms": 0,
            "timestamp_iso": datetime.now(timezone.utc).isoformat(),
            "status": "fallback",
            "source": "bitget_public",
            "error": reason,
        }
