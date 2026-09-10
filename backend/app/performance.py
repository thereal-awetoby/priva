from __future__ import annotations

from typing import Any, Callable


def calculate_unrealized_pnl(
    cycles: list[dict[str, Any]],
    *,
    mark_fetcher: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    positions: list[dict[str, Any]] = []
    unrealized_pnl = 0.0

    for cycle in cycles:
        if cycle.get("status") != "submitted":
            continue
        decision = cycle.get("decision") or {}
        side = decision.get("action")
        if side not in {"buy", "sell"}:
            continue

        ticker = cycle.get("ticker") or {}
        entry_price = float(ticker.get("last_price", 0) or 0)
        risk = cycle.get("risk_check", {}).get("risk", {})
        notional = float(risk.get("notional", 0) or 0)
        if entry_price <= 0 or notional <= 0:
            continue

        mark = mark_fetcher(str(cycle.get("symbol", "")))
        mark_price = float(mark.get("last_price", 0) or 0)
        if mark.get("status") != "live" or mark_price <= 0:
            mark_price = entry_price

        quantity = notional / entry_price
        direction = 1 if side == "buy" else -1
        position_pnl = (mark_price - entry_price) * quantity * direction
        unrealized_pnl += position_pnl
        positions.append(
            {
                "symbol": cycle.get("symbol"),
                "side": side,
                "entry_price": entry_price,
                "mark_price": mark_price,
                "qty": quantity,
                "notional_usd": notional,
                "unrealized_pnl": round(position_pnl, 4),
            }
        )

    rounded_pnl = round(unrealized_pnl, 4)
    return {
        "unrealized_pnl": rounded_pnl,
        "realized_pnl": 0.0,
        "daily_pnl": rounded_pnl,
        "total_pnl": rounded_pnl,
        "currency": "USD",
        "source": "supabase_and_bitget",
        "open_positions": positions,
    }
