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
    ) -> None:
        self.max_position_size = max_position_size
        self.max_daily_loss = max_daily_loss
        self.max_leverage = max_leverage
        self.enabled = enabled

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
                "notional": notional,
                "leverage": leverage,
                "max_position_size": self.max_position_size,
                "max_daily_loss": self.max_daily_loss,
                "max_leverage": self.max_leverage,
            },
        }
