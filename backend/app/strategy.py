from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal
from typing import Any


@dataclass(frozen=True)
class Decision:
    action: Literal["buy", "sell", "hold"]
    size: float
    leverage: float
    reason: str
    signal_strength: float = 0.0


def _momentum_strategy(ticker: dict[str, Any]) -> Decision:
    if ticker.get("status") != "live":
        return Decision("hold", 0.0, 1.0, "market feed unavailable; fallback mode active")

    last_price = float(ticker.get("last_price", 0.0) or 0.0)
    open_price = float(ticker.get("open_price", 0.0) or 0.0)
    if last_price > open_price:
        signal = "buy"
        strength = min(1.0, max(0.0, (last_price - open_price) / max(open_price, 1.0)))
    elif last_price < open_price:
        signal = "sell"
        strength = min(1.0, max(0.0, (open_price - last_price) / max(open_price, 1.0)))
    else:
        signal = "hold"
        strength = 0.0

    return Decision(signal, 1.0 if signal != "hold" else 0.0, 1.0, "simple price-vs-open momentum signal", round(strength, 4))


def _mean_reversion_strategy(ticker: dict[str, Any]) -> Decision:
    if ticker.get("status") != "live":
        return Decision("hold", 0.0, 1.0, "market feed unavailable; fallback mode active")

    last_price = float(ticker.get("last_price", 0.0) or 0.0)
    open_price = float(ticker.get("open_price", 0.0) or 0.0)
    if last_price <= 0 or open_price <= 0:
        return Decision("hold", 0.0, 1.0, "invalid market prices")

    deviation = (last_price - open_price) / open_price
    if deviation >= 0.01:
        return Decision("sell", 1.0, 1.0, "mean reversion: price extended above open", round(min(1.0, deviation), 4))
    if deviation <= -0.01:
        return Decision("buy", 1.0, 1.0, "mean reversion: price extended below open", round(min(1.0, abs(deviation)), 4))
    return Decision("hold", 0.0, 1.0, "mean reversion: price within neutral band")


STRATEGIES = {
    "momentum_breakout": _momentum_strategy,
    "mean_reversion": _mean_reversion_strategy,
}
_active_strategy_id = "momentum_breakout"


def decision_to_dict(decision: Decision) -> dict[str, Any]:
    return {**asdict(decision), "status": "logged"}


def get_active_strategy_id() -> str:
    return _active_strategy_id


def activate_strategy(strategy_id: str) -> bool:
    global _active_strategy_id
    if strategy_id not in STRATEGIES:
        return False
    _active_strategy_id = strategy_id
    return True


def build_signal_from_ticker(ticker: dict[str, Any]) -> dict[str, Any]:
    return decision_to_dict(STRATEGIES[_active_strategy_id](ticker))
