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
    FUTURES_LEVERAGE_PATH = "/api/v2/mix/account/set-leverage"
    FUTURES_FLASH_CLOSE_PATH = "/api/v2/mix/order/close-positions"
    SPOT_ORDER_PATH = "/api/v2/spot/trade/place-order"
    SPOT_ASSETS_PATH = "/api/v2/spot/account/assets"

    @staticmethod
    def _format_size(value: float) -> str:
        if value == int(value):
            return str(int(value))
        return str(value)

    @staticmethod
    def normalize_position_mode(value: Any) -> str | None:
        if value is None:
            return None
        raw = str(value).strip().lower()
        aliases = {
            "one_way": "one_way",
            "one_way_mode": "one_way",
            "single": "one_way",
            "single_mode": "one_way",
            "hedge": "hedge",
            "hedge_mode": "hedge",
            "double": "hedge",
            "double_mode": "hedge",
        }
        return aliases.get(raw, raw)

    @staticmethod
    def normalize_position_side(value: Any) -> str | None:
        if value is None:
            return None
        raw = str(value).strip().lower()
        aliases = {
            "buy": "buy",
            "long": "buy",
            "sell": "sell",
            "short": "sell",
        }
        return aliases.get(raw, raw)

    def __init__(self, *, session: Any = requests) -> None:
        self.api_key = os.getenv("BITGET_API_KEY", "")
        self.api_secret = os.getenv("BITGET_API_SECRET", "")
        self.passphrase = os.getenv("BITGET_API_PASSPHRASE", "")
        configured_mode = os.getenv("BITGET_POSITION_MODE", "one_way")
        self.position_mode = self.normalize_position_mode(configured_mode) or "one_way"
        self.session = session

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_secret and self.passphrase)

    def configure_credentials(self, api_key: str, api_secret: str, passphrase: str) -> None:
        self.api_key = api_key.strip()
        self.api_secret = api_secret.strip()
        self.passphrase = passphrase.strip()

    def clear_credentials(self) -> None:
        self.api_key = ""
        self.api_secret = ""
        self.passphrase = ""

    def set_futures_leverage(self, trade: dict[str, Any]) -> dict[str, Any]:
        leverage = float(trade.get("leverage", 1))
        if leverage <= 0:
            return {"status": "rejected", "message": "leverage must be greater than zero"}

        body = {
            "symbol": str(trade["symbol"]).upper(),
            "productType": "USDT-FUTURES",
            "marginCoin": "USDT",
            "leverage": self._format_size(leverage),
        }
        if self.position_mode == "hedge":
            body["holdSide"] = "long" if str(trade["side"]).lower() == "buy" else "short"

        body_text = json.dumps(body, separators=(",", ":"))
        timestamp = str(int(time.time() * 1000))
        prehash = timestamp + "POST" + self.FUTURES_LEVERAGE_PATH + body_text
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
                f"{self.BASE_URL}{self.FUTURES_LEVERAGE_PATH}",
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
            return {"status": "rejected", "message": exchange.get("msg", str(exc)), "exchange": exchange}
        except requests.RequestException as exc:
            return {"status": "execution_error", "message": str(exc)}

        if payload.get("code") not in (None, "00000", 0, "0"):
            return {"status": "rejected", "message": payload.get("msg", "Bitget leverage rejected"), "exchange": payload}
        return {"status": "submitted", "exchange": payload}

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
            "size": self._format_size(size),
            "side": side,
            "orderType": "market",
            "force": "gtc",
            "clientOid": f"priva_{int(time.time() * 1000)}",
        }
        order_path = self.SPOT_ORDER_PATH if market == "spot" else self.FUTURES_ORDER_PATH
        if market == "futures":
            if str(trade.get("trade_side", "open")).lower() == "open" and not trade.get("reduce_only"):
                leverage_result = self.set_futures_leverage(trade)
                if leverage_result["status"] != "submitted":
                    return leverage_result
            # NOTE: `side` stays plain "buy"/"sell" here. Bitget's V2 place-order
            # endpoint does NOT use a "_single" suffix for one-way mode - that
            # convention only applies to the older V1 API. Sending "sell_single"
            # etc. to this V2 endpoint is invalid and was the root cause of the
            # 40774 / 400172 rejections.
            trade_side = str(trade.get("trade_side", "open")).lower()
            margin_mode = str(trade.get("margin_mode", "isolated")).lower()
            body.update({"productType": "USDT-FUTURES", "marginMode": margin_mode, "marginCoin": "USDT"})
            if trade.get("reduce_only") and self.position_mode != "hedge":
                body["reduceOnly"] = "YES"
            elif self.position_mode == "hedge":
                if trade_side == "close" or trade.get("reduce_only"):
                    body["tradeSide"] = "close"
                else:
                    body["tradeSide"] = trade_side
                position_side = self.normalize_position_side(
                    trade.get("position_side")
                    if trade.get("position_side") is not None
                    else ("buy" if side == "sell" else "sell" if trade.get("reduce_only") else side)
                )
                body["posSide"] = "long" if position_side in {"buy", "long"} else "short"
            elif trade_side != "open":
                body["tradeSide"] = trade_side
                if trade_side == "close":
                    body["posSide"] = "long" if self.normalize_position_side(trade.get("position_side")) == "buy" else "short"
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

    def flash_close_position(self, symbol: str, position_side: str) -> dict[str, Any]:
        if not self.configured:
            return {
                "status": "not_configured",
                "message": "Set BITGET_API_KEY, BITGET_API_SECRET, and BITGET_API_PASSPHRASE in the hosting environment.",
            }

        normalized_side = self.normalize_position_side(position_side)
        if normalized_side not in {"buy", "sell"}:
            return {"status": "rejected", "message": "position_side must be buy/long or sell/short"}

        body = {
            "symbol": str(symbol).upper(),
            "productType": "USDT-FUTURES",
            "holdSide": "long" if normalized_side == "buy" else "short",
        }
        body_text = json.dumps(body, separators=(",", ":"))
        timestamp = str(int(time.time() * 1000))
        prehash = timestamp + "POST" + self.FUTURES_FLASH_CLOSE_PATH + body_text
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
                f"{self.BASE_URL}{self.FUTURES_FLASH_CLOSE_PATH}",
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
                "message": payload.get("msg", "Bitget flash close rejected"),
                "exchange": payload,
            }

        return {
            "status": "submitted",
            "symbol": str(symbol).upper(),
            "position_side": normalized_side,
            "exchange": payload,
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

    def fetch_spot_assets(self) -> dict[str, Any]:
        if not self.configured:
            return {"status": "not_configured", "assets": []}

        path = self.SPOT_ASSETS_PATH
        timestamp = str(int(time.time() * 1000))
        prehash = timestamp + "GET" + path
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
            response = self.session.get(f"{self.BASE_URL}{path}", headers=headers, timeout=15)
            response.raise_for_status()
            payload = response.json()
            if payload.get("code") not in (None, "00000", 0, "0"):
                return {"status": "rejected", "message": payload.get("msg", "Spot assets query rejected"), "assets": []}
            return {"status": "ok", "assets": payload.get("data") or []}
        except requests.HTTPError as exc:
            return {"status": "rejected", "message": str(exc), "assets": []}
        except (requests.RequestException, ValueError) as exc:
            return {"status": "execution_error", "message": str(exc), "assets": []}

    def fetch_account_mode(self, symbol: str = "AAPLUSDT") -> dict[str, Any]:
        """Return the Bitget futures position mode without exposing account data."""
        if not self.configured:
            return {"status": "not_configured"}

        path = "/api/v2/mix/account/account"
        query = f"?symbol={symbol.upper()}&marginCoin=USDT&productType=USDT-FUTURES"
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
                return {"status": "rejected", "message": payload.get("msg", "Account query rejected")}
            data = payload.get("data") or {}
            return {
                "status": "ok",
                "symbol": symbol.upper(),
                "product_type": "USDT-FUTURES",
                "position_mode": self.normalize_position_mode(data.get("posMode")),
            }
        except requests.HTTPError as exc:
            return {"status": "rejected", "message": str(exc)}
        except (requests.RequestException, ValueError) as exc:
            return {"status": "execution_error", "message": str(exc)}