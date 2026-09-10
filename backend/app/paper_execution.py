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

        body = {
            "symbol": str(trade["symbol"]).upper(),
            "size": str(trade["qty"]),
            "side": str(trade["side"]).lower(),
            "orderType": "market",
            "force": "gtc",
            "clientOid": f"priva_{int(time.time() * 1000)}",
        }
        order_path = self.SPOT_ORDER_PATH if market == "spot" else self.FUTURES_ORDER_PATH
        if market == "futures":
            body.update(
                {
                    "productType": "USDT-FUTURES",
                    "marginMode": "isolated",
                    "marginCoin": "USDT",
                    "tradeSide": "open",
                }
            )
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
            "exchange": payload,
            "order_id": (payload.get("data") or {}).get("orderId"),
        }
