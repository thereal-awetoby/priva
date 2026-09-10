from __future__ import annotations

from typing import Any


def build_signal_from_ticker(ticker: dict[str, Any]) -> dict[str, Any]:
    if ticker.get("status") != "live":
        return {
            "action": "hold",
            "reason": "market feed unavailable; fallback mode active",
            "signal_strength": 0.0,
            "status": "logged",
        }

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

    return {
        "action": signal,
        "reason": "simple price-vs-open momentum signal",
        "signal_strength": round(strength, 4),
        "status": "logged",
    }
