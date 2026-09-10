from __future__ import annotations

from typing import Any, Callable


def calculate_unrealized_pnl(
    cycles: list[dict[str, Any]],
    *,
    mark_fetcher: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    open_lots: dict[tuple[str, str], list[dict[str, float]]] = {}
    realized_pnl = 0.0
    unrealized_pnl = 0.0

    if all(cycle.get("created_at") for cycle in cycles):
        ordered_cycles = sorted(cycles, key=lambda cycle: cycle["created_at"])
    else:
        ordered_cycles = cycles

    for cycle in ordered_cycles:
        if cycle.get("status") == "closed":
            order = cycle.get("order_result") or {}
            close_side = order.get("closed_position_side") or (cycle.get("decision") or {}).get("closed_position_side")
            if close_side not in {"buy", "sell"}:
                continue
            symbol = str(cycle.get("symbol", ""))
            exit_price = float(order.get("entry_price", 0) or (cycle.get("ticker") or {}).get("last_price", 0) or 0)
            remaining = float(order.get("qty", 0) or 0)
            lots = open_lots.get((symbol, close_side), [])
            direction = 1 if close_side == "buy" else -1
            while lots and remaining > 0:
                lot = lots[0]
                closed_qty = min(remaining, lot["qty"])
                realized_pnl += (exit_price - lot["entry_price"]) * closed_qty * direction
                lot["qty"] -= closed_qty
                remaining -= closed_qty
                if lot["qty"] <= 0:
                    lots.pop(0)
            continue

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

        symbol = str(cycle.get("symbol", ""))
        quantity = notional / entry_price
        open_lots.setdefault((symbol, side), []).append({"entry_price": entry_price, "qty": quantity})
    positions: list[dict[str, Any]] = []
    for (symbol, side), lots in open_lots.items():
        if not lots:
            continue
        total_qty = sum(lot["qty"] for lot in lots)
        total_notional = sum(lot["qty"] * lot["entry_price"] for lot in lots)
        mark = mark_fetcher(symbol)
        mark_price = float(mark.get("last_price", 0) or 0) if mark.get("status") == "live" else total_notional / total_qty
        direction = 1 if side == "buy" else -1
        position_pnl = (mark_price * total_qty - total_notional) * direction
        unrealized_pnl += position_pnl
        positions.append(
            {
                "symbol": symbol,
                "side": side,
                "entry_price": total_notional / total_qty,
                "mark_price": mark_price,
                "qty": total_qty,
                "notional_usd": total_notional,
                "unrealized_pnl": round(position_pnl, 4),
            }
        )

    rounded_pnl = round(unrealized_pnl, 4)
    return {
        "unrealized_pnl": rounded_pnl,
        "realized_pnl": round(realized_pnl, 4),
        "daily_pnl": round(realized_pnl + rounded_pnl, 4),
        "total_pnl": round(realized_pnl + rounded_pnl, 4),
        "currency": "USD",
        "source": "supabase_and_bitget",
        "open_positions": positions,
    }
