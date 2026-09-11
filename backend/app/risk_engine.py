from __future__ import annotations

from typing import Any


class RiskEngine:
    """Hard-rule safety checks for Priva trade evaluation."""

    def __init__(
        self,
        *,
        max_position_size: float = 25000,
        max_daily_loss: float = 1500,
        max_leverage: float = 5.0,
        enabled: bool = True,
        allowed_symbols: list[str] | None = None,
    ) -> None:
        self.max_position_size = max_position_size
        self.max_daily_loss = max_daily_loss
        self.max_leverage = max_leverage
        self.enabled = enabled
        self.allowed_symbols = self._normalize_symbols(allowed_symbols)

    def _normalize_symbols(self, symbols: list[str] | None) -> list[str] | None:
        if symbols is None:
            return None
        if not isinstance(symbols, list):
            raise ValueError("allowed_symbols must be a list of symbols")
        normalized = []
        for symbol in symbols:
            normalized_symbol = str(symbol).strip().upper()
            if not normalized_symbol:
                continue
            normalized.append(normalized_symbol)
        return normalized or None

    def get_settings(self) -> dict[str, Any]:
        return {
            "max_position_size": self.max_position_size,
            "max_daily_loss": self.max_daily_loss,
            "max_leverage": self.max_leverage,
            "enabled": self.enabled,
            "allowed_symbols": list(self.allowed_symbols) if self.allowed_symbols else [],
        }

    def update_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(settings, dict):
            raise ValueError("settings must be an object")

        supported_keys = {"max_position_size", "max_daily_loss", "max_leverage", "enabled", "allowed_symbols"}
        unsupported = sorted(set(settings) - supported_keys)
        if unsupported:
            raise ValueError(f"unsupported settings: {', '.join(unsupported)}")

        if "max_position_size" in settings:
            self.max_position_size = self._coerce_positive_float(settings["max_position_size"], "max_position_size")
        if "max_daily_loss" in settings:
            self.max_daily_loss = self._coerce_positive_float(settings["max_daily_loss"], "max_daily_loss")
        if "max_leverage" in settings:
            self.max_leverage = self._coerce_positive_float(settings["max_leverage"], "max_leverage")
        if "enabled" in settings:
            if not isinstance(settings["enabled"], bool):
                raise ValueError("enabled must be a boolean")
            self.enabled = settings["enabled"]
        if "allowed_symbols" in settings:
            self.allowed_symbols = self._normalize_symbols(settings["allowed_symbols"])

        return self.get_settings()

    def _coerce_positive_float(self, value: Any, field_name: str) -> float:
        try:
            converted = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be numeric") from exc
        if converted <= 0:
            raise ValueError(f"{field_name} must be greater than zero")
        return converted

    def evaluate_trade(
        self,
        *,
        trade: dict[str, Any],
        current_positions: list[dict[str, Any]],
        current_daily_pnl: float,
    ) -> dict[str, Any]:
        if not self.enabled:
            return {"allowed": False, "reasons": ["risk_engine_disabled"], "risk": {}}

        reasons: list[str] = []
        symbol = str(trade.get("symbol", "")).upper()
        if self.allowed_symbols is not None and symbol not in self.allowed_symbols:
            reasons.append(f"unsupported_symbol:{symbol}")

        notional = float(trade.get("qty", 0)) * float(trade.get("entry_price", 0))
        leverage = float(trade.get("leverage", 1))

        if notional > self.max_position_size:
            reasons.append(f"max_position_size:{notional}>{self.max_position_size}")

        if current_daily_pnl <= -self.max_daily_loss:
            reasons.append(f"max_daily_loss:{current_daily_pnl}>{-self.max_daily_loss}")

        if leverage > self.max_leverage:
            reasons.append(f"max_leverage:{leverage}>{self.max_leverage}")

        for position in current_positions:
            if position.get("symbol") == trade.get("symbol"):
                current_notional = float(position.get("qty", 0)) * float(position.get("entry_price", 0))
                if current_notional + notional > self.max_position_size:
                    reasons.append(f"aggregate_position_limit:{current_notional + notional}>{self.max_position_size}")

        return {
            "allowed": len(reasons) == 0,
            "reasons": reasons,
            "risk": {
                "symbol": symbol,
                "notional": notional,
                "leverage": leverage,
                "max_position_size": self.max_position_size,
                "max_daily_loss": self.max_daily_loss,
                "max_leverage": self.max_leverage,
                "allowed_symbols": list(self.allowed_symbols) if self.allowed_symbols else [],
            },
        }
