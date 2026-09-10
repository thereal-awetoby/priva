from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

import requests


class BitgetPaperExecutionClient:
    """Submit authenticated spot or USDT-futures orders to Bitget paper trading."""

    BASE_URL = "https://api.bitget.com"
    FUTURES_ORDER_PATH = "/api/v2/mix/order/place-order"
    SPOT_ORDER_PATH = "/api/v2/spot/trade/place-order"

    def __init__(self, *, session: Any = requests) -> None:
        self.api_key = os.getenv("BITGET_API_KEY", "")
        self.api_secret = os.getenv("BITGET_API_SECRET", "")
        self.passphrase = os.getenv("BITGET_API_PASSPHRASE", "")
        self.position_mode = os.getenv("BITGET_POSITION_MODE", "one_way").lower()
        self.session = session

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_secret and self.passphrase)

    def place_market_order(self, trade: dict[str, Any]) -> dict[str, Any]:
        if not self.configured:
            return {
                "status": "not_configured",
                "message": "Set BITGET_API_KEY, BITGET_API_SECRET, and BITGET_API_PASSPHRASE in the hosting environment.",
            }

        market = str(trade.get("market", "futures")).lower()
        if market not in {"spot", "futures"}:
            return {"status": "rejected", "message": "market must be spot or futures"}

        side = str(trade["side"]).lower()
        size = float(trade["qty"])
        if market == "spot" and side == "buy":
            size *= float(trade.get("entry_price", 0))

        body = {
            "symbol": str(trade["symbol"]).upper(),
            "size": str(size),
            "side": side,
            "orderType": "market",
            "force": "gtc",
            "clientOid": f"priva_{int(time.time() * 1000)}",
        }
        order_path = self.SPOT_ORDER_PATH if market == "spot" else self.FUTURES_ORDER_PATH
        if market == "futures":
            trade_side = str(trade.get("trade_side", "open")).lower()
            body.update({"productType": "USDT-FUTURES", "marginMode": "isolated", "marginCoin": "USDT"})
            if trade_side == "close" and self.position_mode != "hedge":
                body["reduceOnly"] = "YES"
            else:
                body["tradeSide"] = trade_side
                if trade_side == "close":
                    body["holdSide"] = "long" if trade.get("position_side") == "buy" else "short"
        body_text = json.dumps(body, separators=(",", ":"))
        timestamp = str(int(time.time() * 1000))
        prehash = timestamp + "POST" + order_path + body_text
        signature = base64.b64encode(
            hmac.new(self.api_secret.encode(), prehash.encode(), hashlib.sha256).digest()
        ).decode()
        headers = {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": signature,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
            "paptrading": "1",
        }

        try:
            response = self.session.post(
                f"{self.BASE_URL}{order_path}",
                headers=headers,
                data=body_text,
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.HTTPError as exc:
            try:
                exchange = response.json()
            except ValueError:
                exchange = {"raw": response.text}
            return {
                "status": "rejected",
                "message": exchange.get("msg", str(exc)),
                "exchange": exchange,
            }
        except requests.RequestException as exc:
            return {"status": "execution_error", "message": str(exc)}
        if payload.get("code") not in (None, "00000", 0, "0"):
            return {
                "status": "rejected",
                "message": payload.get("msg", "Bitget paper order rejected"),
                "exchange": payload,
            }

        return {
            "status": "submitted",
            "trade_side": str(trade.get("trade_side", "open")).lower(),
            "side": side,
            "qty": float(trade["qty"]),
            "entry_price": float(trade.get("entry_price", 0) or 0),
            "exchange": payload,
            "order_id": (payload.get("data") or {}).get("orderId"),
        }

    def fetch_futures_positions(self) -> dict[str, Any]:
        if not self.configured:
            return {"status": "not_configured", "positions": []}

        path = "/api/v2/mix/ position/all-position".replace(" ", "")
        query = "?marginCoin=USDT&productType=USDT-FUTURES"
        timestamp = str(int(time.time() * 1000))
        prehash = timestamp + "GET" + path + query
        signature = base64.b64encode(
            hmac.new(self.api_secret.encode(), prehash.encode(), hashlib.sha256).digest()
        ).decode()
        headers = {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": signature,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-PASSPHRASE": self.passphrase,
            "paptrading": "1",
        }

        try:
            response = self.session.get(
                f"{self.BASE_URL}{path}{query}",
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("code") not in (None, "00000", 0, "0"):
                return {"status": "rejected", "message": payload.get("msg", "Position query rejected"), "positions": []}
            return {"status": "ok", "positions": payload.get("data") or []}
        except requests.HTTPError as exc:
            return {"status": "rejected", "message": str(exc), "positions": []}
        except requests.RequestException as exc:
            return {"status": "execution_error", "message": str(exc), "positions": []}
