from __future__ import annotations

import logging
import os
from uuid import uuid4
from typing import Any

import requests

logger = logging.getLogger("priva.supabase")


class SupabaseCycleLogger:
    def __init__(self, *, session: Any = requests, session_id: str | None = None, user_id: str | None = None) -> None:
        self.url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        self.session = session
        self.session_id = session_id or os.getenv("PRIVA_SESSION_ID") or uuid4().hex
        self.user_id = user_id

    @property
    def configured(self) -> bool:
        return bool(self.url and self.service_role_key)

    def log_cycle(self, cycle: dict[str, Any]) -> dict[str, Any]:
        if not self.configured:
            return {"status": "not_configured"}

        record = {
            "session_id": self.session_id,
            "symbol": cycle.get("symbol", "UNKNOWN"),
            "market": cycle.get("market", "futures"),
            "mode": cycle.get("mode", "autonomous"),
            "status": cycle.get("status", "unknown"),
            "decision": cycle.get("decision", {}),
            "ticker": cycle.get("ticker"),
            "risk_check": cycle.get("risk_check"),
            "intent": cycle.get("intent"),
            "order_result": cycle.get("order"),
            "error": cycle.get("error"),
        }
        if cycle.get("created_at"):
            record["created_at"] = cycle["created_at"]
        if self.user_id:
            record["user_id"] = self.user_id
        response = None
        try:
            response = self.session.post(
                f"{self.url}/rest/v1/agent_cycles",
                headers={
                    "apikey": self.service_role_key,
                    "Authorization": f"Bearer {self.service_role_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                json=record,
                timeout=15,
            )
            response.raise_for_status()
            return {"status": "logged"}
        except requests.RequestException as exc:
            detail = str(getattr(response, "text", "") or "").strip()
            message = f"{exc}: {detail}" if detail else str(exc)
            logger.warning("Supabase cycle logging failed: %s", message)
            return {"status": "error", "message": message}

    def log_balance_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        if not self.configured:
            return {"status": "not_configured"}

        record = {
            "session_id": self.session_id,
            "balance": float(snapshot.get("balance", 0) or 0),
            "equity": float(snapshot.get("equity", 0) or 0),
        }
        if snapshot.get("futures_equity") is not None:
            record["futures_equity"] = float(snapshot["futures_equity"] or 0)
        if snapshot.get("spot_equity") is not None:
            record["spot_equity"] = float(snapshot["spot_equity"] or 0)
        if self.user_id:
            record["user_id"] = self.user_id
        try:
            response = self.session.post(
                f"{self.url}/rest/v1/balance_snapshots",
                headers={
                    "apikey": self.service_role_key,
                    "Authorization": f"Bearer {self.service_role_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                json=record,
                timeout=15,
            )
            response.raise_for_status()
            return {"status": "logged"}
        except requests.RequestException as exc:
            logger.warning("Supabase balance snapshot failed: %s", exc)
            return {"status": "error", "message": str(exc)}

    def fetch_balance_snapshots(
        self,
        *,
        limit: int = 1000,
        session_id: str | None = None,
        created_after: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self.configured:
            return []
        try:
            params = {
                "select": "created_at,balance,equity,futures_equity,spot_equity",
                "order": "created_at.asc",
                "limit": min(limit, 1000),
            }
            if session_id:
                params["session_id"] = f"eq.{session_id}"
            if created_after:
                params["created_at"] = f"gte.{created_after}"
            if self.user_id:
                params["user_id"] = f"eq.{self.user_id}"
            response = self.session.get(
                f"{self.url}/rest/v1/balance_snapshots",
                headers={
                    "apikey": self.service_role_key,
                    "Authorization": f"Bearer {self.service_role_key}",
                },
                params=params,
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, list) else []
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Supabase balance snapshot read failed: %s", exc)
            return []

    def fetch_cycles(self, *, limit: int | None = None, session_id: str | None = None) -> list[dict[str, Any]]:
        if not self.configured:
            return []

        try:
            page_size = min(limit, 1000) if limit is not None else 1000
            cycles: list[dict[str, Any]] = []
            offset = 0
            while True:
                params = {
                    "select": "*",
                    "order": "created_at.desc",
                    "limit": page_size,
                    "offset": offset,
                }
                if session_id:
                    params["session_id"] = f"eq.{session_id}"
                if self.user_id:
                    params["user_id"] = f"eq.{self.user_id}"
                response = self.session.get(
                    f"{self.url}/rest/v1/agent_cycles",
                    headers={
                        "apikey": self.service_role_key,
                        "Authorization": f"Bearer {self.service_role_key}",
                    },
                    params=params,
                    timeout=15,
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, list):
                    break
                cycles.extend(payload)
                if len(payload) < page_size or (limit is not None and len(cycles) >= limit):
                    break
                offset += len(payload)
            return cycles[:limit] if limit is not None else cycles
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Supabase cycle read failed: %s", exc)
            return []

    def has_open_position(self, symbol: str, market: str | None = None) -> bool:
        if not self.configured:
            return False

        try:
            params = {
                "select": "id",
                "symbol": f"eq.{symbol.upper()}",
                "status": "eq.submitted",
                "limit": 1,
            }
            if market:
                params["market"] = f"eq.{market.lower()}"
            if self.user_id:
                params["user_id"] = f"eq.{self.user_id}"
            response = self.session.get(
                f"{self.url}/rest/v1/agent_cycles",
                headers={
                    "apikey": self.service_role_key,
                    "Authorization": f"Bearer {self.service_role_key}",
                },
                params=params,
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            return isinstance(payload, list) and bool(payload)
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Supabase position check failed: %s", exc)
            return True

    def fetch_active_strategy(self) -> str | None:
        if not self.configured:
            return None

        try:
            response = self.session.get(
                f"{self.url}/rest/v1/strategy_settings",
                headers={
                    "apikey": self.service_role_key,
                    "Authorization": f"Bearer {self.service_role_key}",
                },
                params={"select": "strategy_id", "id": "eq.global", "limit": 1},
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, list) and payload:
                strategy_id = payload[0].get("strategy_id")
                return str(strategy_id) if strategy_id else None
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Supabase strategy read failed: %s", exc)
        return None

    def save_active_strategy(self, strategy_id: str) -> dict[str, Any]:
        if not self.configured:
            return {"status": "not_configured"}

        try:
            response = self.session.post(
                f"{self.url}/rest/v1/strategy_settings",
                headers={
                    "apikey": self.service_role_key,
                    "Authorization": f"Bearer {self.service_role_key}",
                    "Content-Type": "application/json",
                    "Prefer": "resolution=merge-duplicates,return=minimal",
                },
                params={"on_conflict": "id"},
                json={"id": "global", "strategy_id": strategy_id},
                timeout=15,
            )
            response.raise_for_status()
            return {"status": "saved"}
        except requests.RequestException as exc:
            logger.warning("Supabase strategy write failed: %s", exc)
            return {"status": "error", "message": str(exc)}

    def save_user_credentials(self, user_id: str, encrypted_credentials: str) -> dict[str, Any]:
        if not self.configured:
            return {"status": "not_configured"}
        try:
            response = self.session.post(
                f"{self.url}/rest/v1/user_bitget_credentials",
                headers={
                    "apikey": self.service_role_key,
                    "Authorization": f"Bearer {self.service_role_key}",
                    "Content-Type": "application/json",
                    "Prefer": "resolution=merge-duplicates,return=minimal",
                },
                params={"on_conflict": "user_id"},
                json={"user_id": user_id, "encrypted_credentials": encrypted_credentials},
                timeout=15,
            )
            response.raise_for_status()
            return {"status": "saved"}
        except requests.RequestException as exc:
            logger.warning("Supabase credential save failed: %s", exc)
            return {"status": "error", "message": str(exc)}

    def fetch_user_credentials(self, user_id: str) -> str | None:
        if not self.configured:
            return None
        try:
            response = self.session.get(
                f"{self.url}/rest/v1/user_bitget_credentials",
                headers={
                    "apikey": self.service_role_key,
                    "Authorization": f"Bearer {self.service_role_key}",
                },
                params={"select": "encrypted_credentials", "user_id": f"eq.{user_id}", "limit": 1},
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            return payload[0].get("encrypted_credentials") if isinstance(payload, list) and payload else None
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Supabase credential read failed: %s", exc)
            return None

    def delete_user_credentials(self, user_id: str) -> dict[str, Any]:
        if not self.configured:
            return {"status": "not_configured"}
        try:
            response = self.session.delete(
                f"{self.url}/rest/v1/user_bitget_credentials",
                headers={
                    "apikey": self.service_role_key,
                    "Authorization": f"Bearer {self.service_role_key}",
                },
                params={"user_id": f"eq.{user_id}"},
                timeout=15,
            )
            response.raise_for_status()
            return {"status": "deleted"}
        except requests.RequestException as exc:
            logger.warning("Supabase credential delete failed: %s", exc)
            return {"status": "error", "message": str(exc)}

    def fetch_connected_users(self) -> list[dict[str, Any]]:
        if not self.configured:
            return []
        try:
            response = self.session.get(
                f"{self.url}/rest/v1/user_bitget_credentials",
                headers={
                    "apikey": self.service_role_key,
                    "Authorization": f"Bearer {self.service_role_key}",
                },
                params={"select": "user_id,encrypted_credentials"},
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, list) else []
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Supabase connected-user read failed: %s", exc)
            return []

    def save_user_settings(self, user_id: str, settings: dict[str, Any]) -> dict[str, Any]:
        if not self.configured:
            return {"status": "not_configured"}
        try:
            response = self.session.post(
                f"{self.url}/rest/v1/user_agent_settings",
                headers={
                    "apikey": self.service_role_key,
                    "Authorization": f"Bearer {self.service_role_key}",
                    "Content-Type": "application/json",
                    "Prefer": "resolution=merge-duplicates,return=minimal",
                },
                params={"on_conflict": "user_id"},
                json={"user_id": user_id, **settings},
                timeout=15,
            )
            response.raise_for_status()
            return {"status": "saved"}
        except requests.RequestException as exc:
            logger.warning("Supabase user settings save failed: %s", exc)
            return {"status": "error", "message": str(exc)}

    def fetch_user_settings(self, user_id: str) -> dict[str, Any]:
        if not self.configured:
            return {}
        try:
            response = self.session.get(
                f"{self.url}/rest/v1/user_agent_settings",
                headers={
                    "apikey": self.service_role_key,
                    "Authorization": f"Bearer {self.service_role_key}",
                },
                params={"select": "*", "user_id": f"eq.{user_id}", "limit": 1},
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            return payload[0] if isinstance(payload, list) and payload else {}
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Supabase user settings read failed: %s", exc)
            return {}

    def save_custom_strategy(
        self,
        user_id: str,
        strategy_id: str,
        definition: dict[str, Any],
        name: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        if not self.configured:
            return {"status": "not_configured"}
        try:
            response = self.session.post(
                f"{self.url}/rest/v1/custom_strategies",
                headers={
                    "apikey": self.service_role_key,
                    "Authorization": f"Bearer {self.service_role_key}",
                    "Content-Type": "application/json",
                    "Prefer": "resolution=merge-duplicates,return=minimal",
                },
                params={"on_conflict": "user_id,strategy_id"},
                json={
                    "user_id": user_id,
                    "strategy_id": strategy_id,
                    "name": name,
                    "description": description,
                    "definition": definition,
                },
                timeout=15,
            )
            response.raise_for_status()
            return {"status": "saved"}
        except requests.RequestException as exc:
            logger.warning("Supabase custom strategy write failed: %s", exc)
            return {"status": "error", "message": str(exc)}

    def fetch_custom_strategies(self, user_id: str) -> list[dict[str, Any]]:
        if not self.configured:
            return []
        try:
            response = self.session.get(
                f"{self.url}/rest/v1/custom_strategies",
                headers={
                    "apikey": self.service_role_key,
                    "Authorization": f"Bearer {self.service_role_key}",
                },
                params={"select": "*", "user_id": f"eq.{user_id}"},
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, list) else []
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Supabase custom strategy read failed: %s", exc)
            return []

    def delete_custom_strategy(self, user_id: str, strategy_id: str) -> dict[str, Any]:
        if not self.configured:
            return {"status": "not_configured"}
        try:
            response = self.session.delete(
                f"{self.url}/rest/v1/custom_strategies",
                headers={
                    "apikey": self.service_role_key,
                    "Authorization": f"Bearer {self.service_role_key}",
                },
                params={
                    "user_id": f"eq.{user_id}",
                    "strategy_id": f"eq.{strategy_id}",
                },
                timeout=15,
            )
            response.raise_for_status()
            return {"status": "deleted"}
        except requests.RequestException as exc:
            logger.warning("Supabase custom strategy delete failed: %s", exc)
            return {"status": "error", "message": str(exc)}
