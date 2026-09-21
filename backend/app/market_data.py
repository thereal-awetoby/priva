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
        url = f"{self.BASE_URL}/spot/market/tickers"
        params = {"category": "SPOT"}

        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            payload = response.json()

            if payload.get("code") not in (None, "00000", 0, "0"):
                fallback = self.build_fallback_ticker(symbol, payload.get("msg", "bitget_error"))
                self.last_snapshot = fallback
                return fallback

            data = payload.get("data") or {}
            if isinstance(data, list):
                requested_symbol = symbol.upper()
                data = next(
                    (item for item in data if str(item.get("symbol", "")).upper() == requested_symbol),
                    {},
                )
            if not data:
                return self.fetch_futures_ticker(symbol)

            normalized = self.normalize_ticker_payload(data)
            self.last_snapshot = normalized
            return normalized
        except requests.RequestException as exc:
            logger.warning("Bitget public market fetch failed for %s: %s", symbol, exc)
            fallback = self.build_fallback_ticker(symbol, str(exc))
            self.last_snapshot = fallback
            return fallback

    def fetch_futures_ticker(self, symbol: str) -> dict[str, Any]:
        url = f"{self.BASE_URL}/mix/market/ticker"
        params = {"productType": "USDT-FUTURES", "symbol": symbol.upper()}

        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            payload = response.json()
            if payload.get("code") not in (None, "00000", 0, "0"):
                fallback = self.build_fallback_ticker(symbol, payload.get("msg", "bitget_futures_error"))
                self.last_snapshot = fallback
                return fallback

            data = payload.get("data") or {}
            if isinstance(data, list):
                data = next(
                    (item for item in data if str(item.get("symbol", "")).upper() == symbol.upper()),
                    {},
                )
            if not data:
                fallback = self.build_fallback_ticker(symbol, "empty_data")
                self.last_snapshot = fallback
                return fallback

            normalized = self.normalize_ticker_payload(data)
            normalized["source"] = "bitget_public_futures"
            self.last_snapshot = normalized
            return normalized
        except requests.RequestException as exc:
            logger.warning("Bitget futures market fetch failed for %s: %s", symbol, exc)
            fallback = self.build_fallback_ticker(symbol, str(exc))
            self.last_snapshot = fallback
            return fallback

    def fetch_daily_gap_context(self, symbol: str) -> dict[str, Any]:
        """Return yesterday's close and today's daily open from public futures candles."""
        url = f"{self.BASE_URL}/mix/market/candles"
        params = {
            "productType": "USDT-FUTURES",
            "symbol": symbol.upper(),
            "granularity": "1D",
            "limit": 3,
        }

        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            payload = response.json()
            if payload.get("code") not in (None, "00000", 0, "0"):
                return {"status": "fallback", "symbol": symbol.upper(), "error": payload.get("msg", "bitget_error")}

            rows = payload.get("data") or []
            candles = []
            for row in rows:
                if not isinstance(row, list) or len(row) < 5:
                    continue
                candles.append(
                    {
                        "timestamp_ms": int(row[0]),
                        "open": float(row[1]),
                        "close": float(row[4]),
                    }
                )
            candles.sort(key=lambda candle: candle["timestamp_ms"])
            if len(candles) < 2:
                return {"status": "fallback", "symbol": symbol.upper(), "error": "not_enough_daily_candles"}

            previous, current = candles[-2], candles[-1]
            return {
                "status": "live",
                "symbol": symbol.upper(),
                "previous_close": previous["close"],
                "session_open": current["open"],
                "timestamp_ms": current["timestamp_ms"],
                "source": "bitget_public_futures_candles",
            }
        except (requests.RequestException, ValueError, TypeError, IndexError) as exc:
            logger.warning("Bitget daily candle fetch failed for %s: %s", symbol, exc)
            return {"status": "fallback", "symbol": symbol.upper(), "error": str(exc)}

    def fetch_daily_closes(self, symbol: str, *, limit: int = 60) -> dict[str, Any]:
        """Fetch sorted daily close prices for pair-spread calculations."""
        url = f"{self.BASE_URL}/mix/market/candles"
        params = {
            "productType": "USDT-FUTURES",
            "symbol": symbol.upper(),
            "granularity": "1D",
            "limit": min(max(int(limit), 2), 1000),
        }
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            payload = response.json()
            if payload.get("code") not in (None, "00000", 0, "0"):
                return {"status": "fallback", "symbol": symbol.upper(), "closes": [], "error": payload.get("msg", "bitget_error")}
            candles = []
            for row in payload.get("data") or []:
                if isinstance(row, list) and len(row) >= 5:
                    candles.append((int(row[0]), float(row[4])))
            candles.sort()
            return {
                "status": "live" if len(candles) >= 2 else "fallback",
                "symbol": symbol.upper(),
                "timestamps": [item[0] for item in candles],
                "closes": [item[1] for item in candles],
                "source": "bitget_public_futures_candles",
            }
        except (requests.RequestException, ValueError, TypeError, IndexError) as exc:
            logger.warning("Bitget daily closes fetch failed for %s: %s", symbol, exc)
            return {"status": "fallback", "symbol": symbol.upper(), "closes": [], "error": str(exc)}

    def fetch_pair_daily_closes(self, first_symbol: str, second_symbol: str, *, limit: int = 60) -> dict[str, Any]:
        first = self.fetch_daily_closes(first_symbol, limit=limit)
        second = self.fetch_daily_closes(second_symbol, limit=limit)
        if first.get("status") != "live" or second.get("status") != "live":
            return {"status": "fallback", "symbols": [first_symbol.upper(), second_symbol.upper()], "error": "pair_candle_data_unavailable"}
        return {
            "status": "live",
            "symbols": [first_symbol.upper(), second_symbol.upper()],
            "first": first,
            "second": second,
        }

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
        last_price = float(payload.get("last", payload.get("lastPr", 0)) or 0)
        open_price = float(payload.get("open", payload.get("open24h", 0)) or 0)
        high_24h = float(payload.get("high", payload.get("high24h", 0)) or 0)
        low_24h = float(payload.get("low", payload.get("low24h", 0)) or 0)
        base_volume = float(payload.get("baseVolume", 0) or 0)
        quote_volume = float(payload.get("quoteVolume", payload.get("usdtVolume", 0)) or 0)
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
