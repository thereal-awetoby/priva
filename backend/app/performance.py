from __future__ import annotations

from typing import Any, Callable


def _as_float(*values: Any, default: float = 0.0) -> float:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _close_qty(order: dict[str, Any], cycle: dict[str, Any], exit_price: float) -> float:
    qty = _as_float(
        order.get("qty"),
        order.get("size"),
        (cycle.get("decision") or {}).get("size"),
        (cycle.get("decision") or {}).get("qty"),
    )
    if qty > 0:
        return qty
    notional = _as_float(
        order.get("notional"),
        order.get("position_size_usd"),
        ((cycle.get("risk_check") or {}).get("risk") or {}).get("notional"),
    )
    if notional > 0 and exit_price > 0:
        inferred = notional / exit_price
        if inferred > 0:
            return inferred
    # Tokenized stocks on this desk are almost always 1 unit when qty was not logged.
    return 1.0 if exit_price > 0 else 0.0


def _close_side(order: dict[str, Any], cycle: dict[str, Any]) -> str | None:
    side = order.get("closed_position_side") or (cycle.get("decision") or {}).get(
        "closed_position_side"
    )
    if side in {"buy", "sell"}:
        return side
    action = (cycle.get("decision") or {}).get("action")
    if action in {"buy", "sell"}:
        return action
    return None


def _match_lots(
    open_lots: dict[tuple[str, str, str], list[dict[str, float]]],
    symbol: str,
    market: str,
    side: str | None,
) -> tuple[str, list[dict[str, float]]]:
    if side in {"buy", "sell"}:
        exact = open_lots.get((symbol, market, side), [])
        if exact:
            return side, exact
        for (lot_symbol, _lot_market, lot_side), lots in open_lots.items():
            if lot_symbol == symbol and lot_side == side and lots:
                return side, lots
    for (lot_symbol, lot_market, lot_side), lots in open_lots.items():
        if lot_symbol == symbol and lot_market == market and lots:
            return lot_side, lots
    for (lot_symbol, _lot_market, lot_side), lots in open_lots.items():
        if lot_symbol == symbol and lots:
            return lot_side, lots
    return side or "buy", []


def _reconstruct_trade_history(
    cycles: list[dict[str, Any]],
) -> tuple[list[float | None], dict[tuple[str, str, str], list[dict[str, float]]]]:
    open_lots: dict[tuple[str, str, str], list[dict[str, float]]] = {}
    last_entry: dict[str, dict[str, float]] = {}
    realized_by_cycle: list[float | None] = [None] * len(cycles)
    ordered_cycles = list(enumerate(cycles))
    if all(cycle.get("created_at") for cycle in cycles):
        ordered_cycles.sort(key=lambda item: item[1]["created_at"])

    for cycle_index, cycle in ordered_cycles:
        if cycle.get("mode") == "autonomous" and (cycle.get("ticker") or {}).get("status") == "historical":
            continue
        symbol = str(cycle.get("symbol", "")).upper()
        market = str(cycle.get("market", "futures")).lower()
        if cycle.get("status") == "closed":
            order = cycle.get("order_result") or cycle.get("order") or {}
            exchange_pnl = order.get("exchange_realized_pnl")
            if exchange_pnl is None:
                exchange_pnl = order.get("profit") or order.get("realizedPnl") or order.get("realizedPL")
            if exchange_pnl is not None:
                realized_by_cycle[cycle_index] = float(exchange_pnl or 0)

            exit_price = _as_float(
                order.get("exit_price"),
                order.get("entry_price"),
                (cycle.get("ticker") or {}).get("last_price"),
            )
            remaining = _close_qty(order, cycle, exit_price)
            side = _close_side(order, cycle)
            matched_side, lots = _match_lots(open_lots, symbol, market, side)
            direction = 1 if matched_side == "buy" else -1
            reconstructed_pnl = 0.0
            matched_qty = 0.0
            if remaining > 0 and exit_price > 0:
                to_close = remaining
                while lots and to_close > 0:
                    lot = lots[0]
                    closed_qty = min(to_close, lot["qty"])
                    reconstructed_pnl += (exit_price - lot["entry_price"]) * closed_qty * direction
                    lot["qty"] -= closed_qty
                    to_close -= closed_qty
                    matched_qty += closed_qty
                    if lot["qty"] <= 1e-12:
                        lots.pop(0)

            if realized_by_cycle[cycle_index] is None:
                if matched_qty > 0:
                    realized_by_cycle[cycle_index] = reconstructed_pnl
                elif symbol in last_entry and exit_price > 0:
                    prior = last_entry[symbol]
                    fallback_qty = remaining if remaining > 0 else prior["qty"]
                    fallback_dir = 1 if prior["side"] == "buy" else -1
                    realized_by_cycle[cycle_index] = (
                        (exit_price - prior["entry_price"]) * fallback_qty * fallback_dir
                    )
                else:
                    # Close logged with no matching open and no exchange PnL.
                    # Show 0 rather than a blank cell.
                    realized_by_cycle[cycle_index] = 0.0
            continue

        if cycle.get("status") != "submitted":
            continue
        decision = cycle.get("decision") or {}
        side = decision.get("action")
        if side not in {"buy", "sell"}:
            continue

        ticker = cycle.get("ticker") or {}
        order = cycle.get("order_result") or cycle.get("order") or {}
        entry_price = _as_float(
            order.get("entry_price"),
            ticker.get("last_price"),
        )
        risk = (cycle.get("risk_check") or {}).get("risk") or {}
        notional = _as_float(risk.get("notional"), order.get("notional"), order.get("position_size_usd"))
        quantity = _as_float(order.get("qty"), decision.get("size"))
        if quantity <= 0 and entry_price > 0 and notional > 0:
            quantity = notional / entry_price
        if quantity <= 0:
            quantity = 1.0
        if entry_price <= 0:
            continue

        open_lots.setdefault((symbol, market, side), []).append(
            {"entry_price": entry_price, "qty": quantity}
        )
        last_entry[symbol] = {"entry_price": entry_price, "qty": quantity, "side": side}

    return realized_by_cycle, open_lots


def calculate_closed_trade_pnls(cycles: list[dict[str, Any]]) -> list[float | None]:
    realized_by_cycle, _ = _reconstruct_trade_history(cycles)
    return realized_by_cycle


def calculate_unrealized_pnl(
    cycles: list[dict[str, Any]],
    *,
    mark_fetcher: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    realized_by_cycle, open_lots = _reconstruct_trade_history(cycles)
    realized_pnl = sum(pnl for pnl in realized_by_cycle if pnl is not None)
    unrealized_pnl = 0.0

    positions: list[dict[str, Any]] = []
    for (symbol, market, side), lots in open_lots.items():
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
                "market": market,
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