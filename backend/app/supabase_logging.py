from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger("priva.supabase")


class SupabaseCycleLogger:
    def __init__(self, *, session: Any = requests) -> None:
        self.url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        self.session = session

    @property
    def configured(self) -> bool:
        return bool(self.url and self.service_role_key)

    def log_cycle(self, cycle: dict[str, Any]) -> dict[str, Any]:
        if not self.configured:
            return {"status": "not_configured"}

        record = {
            "symbol": cycle.get("symbol", "UNKNOWN"),
            "status": cycle.get("status", "unknown"),
            "decision": cycle.get("decision", {}),
            "ticker": cycle.get("ticker"),
            "risk_check": cycle.get("risk_check"),
            "intent": cycle.get("intent"),
            "order_result": cycle.get("order"),
            "error": cycle.get("error"),
        }
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
            logger.warning("Supabase cycle logging failed: %s", exc)
            return {"status": "error", "message": str(exc)}
