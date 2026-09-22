from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

from app.strategy import build_pairs_signal, build_signal_from_ticker, get_active_strategy_id

logger = logging.getLogger("priva.agent_loop")
logger.setLevel(logging.INFO)
LOOP_INTERVAL_SECONDS = int(os.getenv("AGENT_LOOP_INTERVAL_SECONDS", "300"))
MARKET_TYPE = os.getenv("AGENT_MARKET_TYPE", "futures").strip().lower()
if MARKET_TYPE not in {"spot", "futures"}:
    MARKET_TYPE = "futures"
TAKE_PROFIT_PCT = float(os.getenv("AGENT_TAKE_PROFIT_PCT", "5"))
STOP_LOSS_PCT = float(os.getenv("AGENT_STOP_LOSS_PCT", "2"))
CLOSE_ON_SIGNAL_VIOLATION = os.getenv("AGENT_CLOSE_ON_SIGNAL_VIOLATION", "true").lower() == "true"
WATCHED_SYMBOLS = [
    symbol.strip().upper()
    for symbol in os.getenv("AGENT_WATCHED_SYMBOLS", "AAPLUSDT,TSLAUSDT").split(",")
    if symbol.strip().upper() in {"AAPLUSDT", "TSLAUSDT"}
]
ORDER_QTY = float(os.getenv("AGENT_ORDER_QTY", "1"))
SUPPORTED_SYMBOLS = {"AAPLUSDT", "TSLAUSDT"}
MODE = "autonomous"

_loop_task: asyncio.Task | None = None
_stop_event = asyncio.Event()
_recent_cycles: list[dict[str, Any]] = []
_recent_balance_snapshots: list[dict[str, Any]] = []


def _record_cycle(entry: dict[str, Any]) -> None:
    _recent_cycles.append(entry)
    del _recent_cycles[:-1000]


def recent_cycles() -> list[dict[str, Any]]:
    return list(_recent_cycles)


def recent_balance_snapshots() -> list[dict[str, Any]]:
    return list(_recent_balance_snapshots)


def configure_watched_symbols(symbols: list[str]) -> list[str]:
    global WATCHED_SYMBOLS
    WATCHED_SYMBOLS = [symbol.upper() for symbol in symbols if symbol.upper() in SUPPORTED_SYMBOLS]
    return list(WATCHED_SYMBOLS)


def configure_mode(mode: str) -> str:
    global MODE
    normalized = str(mode).strip().lower()
    if normalized not in {"autonomous", "strategy"}:
        raise ValueError("mode must be autonomous or strategy")
    MODE = normalized
    return MODE


def configure_market_type(market: str) -> str:
    global MARKET_TYPE
    normalized = str(market).strip().lower()
    if normalized not in {"spot", "futures"}:
        raise ValueError("market must be spot or futures")
    MARKET_TYPE = normalized
    return MARKET_TYPE


def configure_exit_rules(
    *,
    take_profit_pct: float | None = None,
    stop_loss_pct: float | None = None,
    close_on_signal_violation: bool | None = None,
) -> dict[str, Any]:
    global TAKE_PROFIT_PCT, STOP_LOSS_PCT, CLOSE_ON_SIGNAL_VIOLATION
    if take_profit_pct is not None:
        if take_profit_pct <= 0:
            raise ValueError("take_profit_pct must be greater than zero")
        TAKE_PROFIT_PCT = float(take_profit_pct)
    if stop_loss_pct is not None:
        if stop_loss_pct <= 0:
            raise ValueError("stop_loss_pct must be greater than zero")
        STOP_LOSS_PCT = float(stop_loss_pct)
    if close_on_signal_violation is not None:
        CLOSE_ON_SIGNAL_VIOLATION = close_on_signal_violation
    return get_exit_rules()


def get_exit_rules() -> dict[str, Any]:
    return {
        "take_profit_pct": TAKE_PROFIT_PCT,
        "stop_loss_pct": STOP_LOSS_PCT,
        "close_on_signal_violation": CLOSE_ON_SIGNAL_VIOLATION,
    }


def build_encrypted_intent(symbol: str, decision: dict[str, Any], risk_result: dict[str, Any]) -> dict[str, Any]:
    intent = {
        "symbol": symbol.upper(),
        "action": decision["action"],
        "signal_strength": decision["signal_strength"],
        "risk_notional": risk_result["risk"].get("notional", 0.0),
    }
    serialized = json.dumps(intent, sort_keys=True, separators=(",", ":")).encode()
    return {"intent_hash": hashlib.sha256(serialized).hexdigest(), "intent": intent}


def _logged_spot_entry(symbol: str, cycle_logger: Any | None) -> dict[str, Any] | None:
    cycles = cycle_logger.fetch_cycles() if cycle_logger is not None and callable(getattr(cycle_logger, "fetch_cycles", None)) else recent_cycles()
    if not cycles:
        cycles = recent_cycles()
    open_lots: list[dict[str, float | str]] = []
    for cycle in sorted(cycles, key=lambda item: item.get("created_at", "")):
        if cycle.get("symbol", "").upper() != symbol.upper() or cycle.get("market", "spot") != "spot":
            continue
        decision = cycle.get("decision") or {}
        side = decision.get("action")
        ticker = cycle.get("ticker") or {}
        price = float(ticker.get("last_price", 0) or 0)
        qty = float((cycle.get("order") or cycle.get("order_result") or {}).get("qty", 0) or 0)
        if cycle.get("status") == "submitted" and side in {"buy", "sell"} and price > 0 and qty > 0:
            open_lots.append({"side": side, "qty": qty, "entry_price": price})
        elif cycle.get("status") == "closed":
            open_lots.clear()
    if not open_lots:
        return None
    side = str(open_lots[-1]["side"])
    quantity = sum(float(lot["qty"]) for lot in open_lots if lot["side"] == side)
    notional = sum(float(lot["qty"]) * float(lot["entry_price"]) for lot in open_lots if lot["side"] == side)
    return {"symbol": symbol.upper(), "qty": quantity, "entry_price": notional / quantity, "side": side, "unrealized_pnl": 0.0}


def _logged_futures_entry(symbol: str, cycle_logger: Any | None) -> dict[str, Any] | None:
    cycles = cycle_logger.fetch_cycles() if cycle_logger is not None and callable(getattr(cycle_logger, "fetch_cycles", None)) else recent_cycles()
    if not cycles:
        cycles = recent_cycles()
    open_lots: list[dict[str, float | str]] = []
    for cycle in sorted(cycles, key=lambda item: item.get("created_at", "")):
        if cycle.get("symbol", "").upper() != symbol.upper() or cycle.get("market", "futures") != "futures":
            continue
        decision = cycle.get("decision") or {}
        side = decision.get("action")
        ticker = cycle.get("ticker") or {}
        price = float(ticker.get("last_price", 0) or 0)
        order = cycle.get("order") or cycle.get("order_result") or {}
        qty = float(order.get("qty", 0) or 0)
        if cycle.get("status") == "submitted" and side in {"buy", "sell"} and price > 0 and qty > 0:
            open_lots.append({"side": side, "qty": qty, "entry_price": price})
        elif cycle.get("status") == "closed":
            open_lots.clear()
    if not open_lots:
        return None
    side = str(open_lots[-1]["side"])
    quantity = sum(float(lot["qty"]) for lot in open_lots if lot["side"] == side)
    notional = sum(float(lot["qty"]) * float(lot["entry_price"]) for lot in open_lots if lot["side"] == side)
    return {
        "symbol": symbol.upper(),
        "qty": quantity,
        "entry_price": notional / quantity,
        "side": side,
        "unrealized_pnl": 0.0,
        "source": "cycle_log_fallback",
    }


def _live_position(symbol: str, execution_client: Any, *, market: str = "futures", cycle_logger: Any | None = None) -> dict[str, Any] | None:
    if market == "spot":
        fetch_assets = getattr(execution_client, "fetch_spot_assets", None)
        if callable(fetch_assets):
            result = fetch_assets()
            if result.get("status") == "ok":
                base_coin = symbol.upper().removesuffix("USDT")
                asset = next((item for item in result.get("assets", []) if str(item.get("coin", "")).upper() == base_coin), None)
                quantity = float((asset or {}).get("available", (asset or {}).get("total", 0)) or 0)
                logged = _logged_spot_entry(symbol, cycle_logger)
                if quantity > 0 and logged:
                    logged["qty"] = quantity
                    return logged
        return None

    fetch_positions = getattr(execution_client, "fetch_futures_positions", None)
    if not callable(fetch_positions):
        return None

    try:
        result = fetch_positions()
    except Exception as exc:
        logger.warning("Live position check failed for %s: %s", symbol, exc)
        return _logged_futures_entry(symbol, cycle_logger)

    if result.get("status") != "ok":
        return _logged_futures_entry(symbol, cycle_logger)

    target_symbol = symbol.upper()
    for position in result.get("positions", []):
        if str(position.get("symbol", "")).upper() != target_symbol:
            continue
        quantity = float(position.get("total", position.get("available", 0)) or 0)
        if quantity <= 0:
            continue
        hold_side = str(position.get("holdSide", position.get("side", ""))).lower()
        return {
            "symbol": target_symbol,
            "qty": quantity,
            "entry_price": float(position.get("openPriceAvg", position.get("entry_price", 0)) or 0),
            "side": "buy" if hold_side in {"long", "buy"} else "sell",
            "unrealized_pnl": float(position.get("unrealizedPL", position.get("unrealized_pnl", 0)) or 0),
        }
    return None


def _live_position_state(symbol: str, execution_client: Any) -> bool | None:
    fetch_positions = getattr(execution_client, "fetch_futures_positions", None)
    if not callable(fetch_positions):
        return None

    try:
        result = fetch_positions()
    except Exception as exc:
        logger.warning("Live position check failed for %s: %s", symbol, exc)
        return None

    if result.get("status") != "ok":
        return None
    target_symbol = symbol.upper()
    return any(
        str(position.get("symbol", "")).upper() == target_symbol
        and float(position.get("total", position.get("available", 0)) or 0) > 0
        for position in result.get("positions", [])
    )


def _close_live_position(
    symbol: str,
    position: dict[str, Any],
    *,
    market: str,
    execution_client: Any,
) -> dict[str, Any]:
    if market == "futures":
        close_position = getattr(execution_client, "flash_close_position", None)
        if not callable(close_position):
            return {"status": "rejected", "message": "futures close is unavailable"}
        return close_position(symbol, position["side"])

    close_order = {
        "symbol": symbol.upper(),
        "side": "sell" if position["side"] == "buy" else "buy",
        "qty": position["qty"],
        "entry_price": position["entry_price"],
        "leverage": 1.0,
        "market": "spot",
        "trade_side": "close",
    }
    return execution_client.place_market_order(close_order)


async def run_cycle(
    symbol: str,
    *,
    market_service: Any,
    risk_engine: Any,
    execution_client: Any,
    cycle_logger: Any | None = None,
    market_type: str | None = None,
    strategy_id: str | None = None,
    strategy_by_symbol: dict[str, str] | None = None,
    take_profit_pct: float | None = None,
    stop_loss_pct: float | None = None,
    close_on_signal_violation: bool | None = None,
    mode: str | None = None,
) -> dict[str, Any]:
    def persist(result: dict[str, Any]) -> dict[str, Any]:
        result.setdefault("created_at", cycle_start.isoformat())
        _record_cycle(result)
        if cycle_logger is not None:
            result["persistence"] = cycle_logger.log_cycle(result)
            fetch_balance = getattr(execution_client, "fetch_futures_account_balance", None)
            log_snapshot = getattr(cycle_logger, "log_balance_snapshot", None)
            if callable(fetch_balance):
                try:
                    balance = fetch_balance()
                    if balance.get("status") == "ok":
                        snapshot = {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "balance": float(balance.get("equity", 0) or 0),
                            "equity": float(balance.get("equity", 0) or 0),
                        }
                        _recent_balance_snapshots.append(snapshot)
                        del _recent_balance_snapshots[:-1000]
                        if callable(log_snapshot):
                            log_snapshot(snapshot)
                except Exception as exc:
                    logger.warning("Balance snapshot failed: %s", exc)
        return result


    cycle_start = datetime.now(timezone.utc)
    normalized_symbol = symbol.upper()
    if normalized_symbol not in SUPPORTED_SYMBOLS:
        result = {
            "status": "blocked",
            "symbol": normalized_symbol,
            "mode": mode or ("strategy" if strategy_id else "autonomous"),
            "decision": {"action": "hold", "symbol": normalized_symbol},
            "risk_check": {"allowed": False, "reasons": [f"unsupported_symbol:{normalized_symbol}"]},
            "order": None,
        }
        _record_cycle(result)
        if cycle_logger is not None:
            result["persistence"] = cycle_logger.log_cycle(result)
        return result
    try:
        ticker = await asyncio.to_thread(market_service.fetch_spot_ticker, symbol)
        ticker = {**ticker, "symbol": symbol.upper()}
        selected_strategy = (strategy_by_symbol or {}).get(symbol.upper(), strategy_id)
        cycle_mode = mode or ("strategy" if selected_strategy else MODE)
        if selected_strategy == "overnight_gap":
            fetch_gap_context = getattr(market_service, "fetch_daily_gap_context", None)
            if not callable(fetch_gap_context):
                ticker["status"] = "fallback"
            else:
                gap_context = await asyncio.to_thread(fetch_gap_context, symbol)
                if gap_context.get("status") == "live":
                    ticker.update(gap_context)
                else:
                    ticker["status"] = "fallback"
        decision = build_signal_from_ticker(ticker, strategy_id=selected_strategy) if selected_strategy else build_signal_from_ticker(ticker)
        decision.update({"symbol": symbol.upper(), "market_status": ticker.get("status", "unknown")})

        if ticker.get("status") != "live":
            result = {
                "status": "logged",
                "symbol": symbol.upper(),
                "mode": cycle_mode,
                "decision": decision,
                "ticker": ticker,
                "risk_check": {"allowed": False, "reasons": ["no_trade_signal"]},
                "order": None,
            }
            return persist(result)

        configured_market = market_type or MARKET_TYPE
        if decision["action"] == "hold":
            markets_to_check = ["futures", "spot"] if configured_market == "autonomous" else [configured_market]
            for exit_market in markets_to_check:
                live_position = _live_position(
                    symbol,
                    execution_client,
                    market=exit_market,
                    cycle_logger=cycle_logger,
                )
                if not live_position:
                    continue
                entry_price = live_position["entry_price"]
                current_price = float(ticker.get("last_price", 0.0) or 0.0)
                price_change_pct = (
                    ((current_price - entry_price) / entry_price) * 100
                    if live_position["side"] == "buy" and entry_price > 0
                    else ((entry_price - current_price) / entry_price) * 100
                    if live_position["side"] == "sell" and entry_price > 0
                    else 0.0
                )
                take_profit = float(decision.get("take_profit_pct") or take_profit_pct or TAKE_PROFIT_PCT)
                stop_loss = float(decision.get("stop_loss_pct") or stop_loss_pct or STOP_LOSS_PCT)
                exit_reason = "take_profit" if price_change_pct >= take_profit else "stop_loss" if price_change_pct <= -stop_loss else None
                if exit_reason:
                    close_result = await asyncio.to_thread(
                        _close_live_position,
                        symbol,
                        live_position,
                        market=exit_market,
                        execution_client=execution_client,
                    )
                    close_result = {
                        **close_result,
                        "closed_position_side": live_position["side"],
                        "qty": live_position["qty"],
                        "entry_price": live_position["entry_price"],
                        "exit_price": current_price,
                    }
                    result = {
                        "status": "closed" if close_result.get("status") == "submitted" else close_result.get("status", "close_failed"),
                        "symbol": symbol.upper(),
                        "mode": cycle_mode,
                        "decision": decision,
                        "ticker": ticker,
                        "exit_reason": exit_reason,
                        "position": live_position,
                        "order": close_result,
                    }
                    return persist(result)
                break

            result = {
                "status": "logged",
                "symbol": symbol.upper(),
                "mode": cycle_mode,
                "decision": decision,
                "ticker": ticker,
                "risk_check": {"allowed": False, "reasons": ["no_trade_signal"]},
                "order": None,
            }
            return persist(result)

        selected_market = decision.get("market") if configured_market == "autonomous" else configured_market
        if selected_market not in {"spot", "futures"}:
            raise ValueError("agent decision must select spot or futures")
        trade = {
            "symbol": symbol.upper(),
            "side": decision["action"],
            "qty": float(decision.get("size") or ORDER_QTY),
            "entry_price": float(ticker.get("last_price", 0.0) or 0.0),
            "leverage": float(decision.get("leverage", 1.0) or 1.0),
            "market": selected_market,
        }
        live_position = _live_position(symbol, execution_client, market=selected_market, cycle_logger=cycle_logger)
        live_position_state = True if live_position else _live_position_state(symbol, execution_client)
        has_existing_position = live_position_state is True or (
            live_position_state is None
            and cycle_logger is not None
            and cycle_logger.has_open_position(symbol)
        )
        if has_existing_position:
            if live_position:
                entry_price = live_position["entry_price"]
                current_price = float(ticker.get("last_price", 0.0) or 0.0)
                price_change_pct = (
                    ((current_price - entry_price) / entry_price) * 100
                    if live_position["side"] == "buy" and entry_price > 0
                    else ((entry_price - current_price) / entry_price) * 100
                    if live_position["side"] == "sell" and entry_price > 0
                    else 0.0
                )
                opposite_signal = decision["action"] in {"buy", "sell"} and decision["action"] != live_position["side"]
                take_profit = float(decision.get("take_profit_pct") or take_profit_pct or TAKE_PROFIT_PCT)
                stop_loss = float(decision.get("stop_loss_pct") or stop_loss_pct or STOP_LOSS_PCT)
                exit_reason = None
                if price_change_pct >= take_profit:
                    exit_reason = "take_profit"
                elif price_change_pct <= -stop_loss:
                    exit_reason = "stop_loss"
                elif (CLOSE_ON_SIGNAL_VIOLATION if close_on_signal_violation is None else close_on_signal_violation) and opposite_signal:
                    exit_reason = "signal_violation"

                if exit_reason:
                    close_result = await asyncio.to_thread(
                        _close_live_position,
                        symbol,
                        live_position,
                        market=selected_market,
                        execution_client=execution_client,
                    )
                    close_result = {
                        **close_result,
                        "closed_position_side": live_position["side"],
                        "qty": live_position["qty"],
                        "entry_price": live_position["entry_price"],
                        "exit_price": current_price,
                    }
                    result = {
                        "status": "closed" if close_result.get("status") == "submitted" else close_result.get("status", "close_failed"),
                        "symbol": symbol.upper(),
                        "mode": cycle_mode,
                        "decision": decision,
                        "ticker": ticker,
                        "exit_reason": exit_reason,
                        "position": live_position,
                        "order": close_result,
                    }
                    return persist(result)

            can_add_to_position = bool(
                live_position
                and live_position["unrealized_pnl"] > 0
                and live_position["side"] == decision["action"]
            )
            if not can_add_to_position:
                result = {
                    "status": "skipped_existing_position",
                    "symbol": symbol.upper(),
                    "mode": cycle_mode,
                    "decision": decision,
                    "ticker": ticker,
                    "order": None,
                    "reason": "existing position is not profitable or signal is not same-direction",
                }
                return persist(result)

        current_positions = []
        if live_position:
            current_positions.append(live_position)
        risk_result = risk_engine.evaluate_trade(
            trade=trade,
            current_positions=current_positions,
            current_daily_pnl=0.0,
        )
        if not risk_result["allowed"]:
            result = {
                "status": "risk_rejected",
                "symbol": symbol.upper(),
                "mode": cycle_mode,
                "decision": decision,
                "ticker": ticker,
                "risk_check": risk_result,
                "order": None,
            }
            return persist(result)

        intent = build_encrypted_intent(symbol, decision, risk_result)
        order_result = await asyncio.to_thread(execution_client.place_market_order, trade)
        result = {
            "status": order_result.get("status", "unknown"),
            "symbol": symbol.upper(),
            "mode": cycle_mode,
            "decision": decision,
            "ticker": ticker,
            "risk_check": risk_result,
            "intent": intent,
            "order": order_result,
            "market": selected_market,
            "duration_seconds": round((datetime.now(timezone.utc) - cycle_start).total_seconds(), 3),
        }
        persist(result)
        logger.info("[%s] autonomous cycle status=%s order_id=%s", symbol, result["status"], order_result.get("order_id"))
        return result
    except Exception as exc:
        logger.exception("[%s] cycle failed: %s", symbol, exc)
        result = {"status": "error", "symbol": symbol.upper(), "error": str(exc)}
        persist(result)
        return result


async def run_pair_cycle(
    first_symbol: str,
    second_symbol: str,
    *,
    market_service: Any,
    risk_engine: Any,
    execution_client: Any,
    cycle_logger: Any | None = None,
    market_type: str = "futures",
    qty: float = 1.0,
    entry_zscore: float = 2.0,
    exit_zscore: float = 0.5,
    stop_loss_pct: float = 2.0,
) -> dict[str, Any]:
    """Evaluate and execute both legs of a pairs trade as one cycle."""
    cycle_start = datetime.now(timezone.utc)
    symbols = [first_symbol.upper(), second_symbol.upper()]
    if symbols not in (["AAPLUSDT", "TSLAUSDT"], ["TSLAUSDT", "AAPLUSDT"]):
        return {"status": "blocked", "strategy_id": "pairs_trading", "symbols": symbols, "reason": "unsupported_pair"}
    if market_type not in {"spot", "futures"} or qty <= 0:
        return {"status": "rejected", "strategy_id": "pairs_trading", "reason": "invalid_pair_configuration"}

    fetch_pair = getattr(market_service, "fetch_pair_daily_closes", None)
    if not callable(fetch_pair):
        return {"status": "logged", "strategy_id": "pairs_trading", "symbols": symbols, "reason": "pair_candle_data_unavailable"}
    history = await asyncio.to_thread(fetch_pair, first_symbol, second_symbol)
    if history.get("status") != "live":
        return {"status": "logged", "strategy_id": "pairs_trading", "symbols": symbols, "reason": history.get("error", "pair_candle_data_unavailable")}

    signal = build_pairs_signal(
        first_symbol,
        second_symbol,
        history["first"].get("closes", []),
        history["second"].get("closes", []),
        entry_zscore=entry_zscore,
        exit_zscore=exit_zscore,
    )
    live_positions = {
        symbol: _live_position(symbol, execution_client, market=market_type, cycle_logger=cycle_logger)
        for symbol in symbols
    }
    open_positions = [position for position in live_positions.values() if position]
    result: dict[str, Any] = {
        "strategy_id": "pairs_trading",
        "symbols": symbols,
        "market": market_type,
        "decision": signal,
        "created_at": cycle_start.isoformat(),
    }

    if open_positions and len(open_positions) != 2:
        result["status"] = "pair_incomplete"
        result["reason"] = "one pair leg is open; refusing to add another leg"
        result["positions"] = live_positions
        return result

    if len(open_positions) == 2:
        current_prices = {
            first_symbol.upper(): float(history["first"]["closes"][-1]),
            second_symbol.upper(): float(history["second"]["closes"][-1]),
        }
        combined_pnl = sum(
            position["qty"] * (current_prices[symbol] - position["entry_price"])
            if position["side"] == "buy"
            else position["qty"] * (position["entry_price"] - current_prices[symbol])
            for symbol, position in live_positions.items()
            if position
        )
        entry_notional = sum(position["qty"] * position["entry_price"] for position in open_positions)
        loss_limit = -(entry_notional * stop_loss_pct / 100) if stop_loss_pct > 0 else float("-inf")
        if signal["action"] == "exit_pair" or combined_pnl <= loss_limit:
            close_results = []
            for symbol, position in live_positions.items():
                close_results.append(
                    await asyncio.to_thread(
                        _close_live_position,
                        symbol,
                        position,
                        market=market_type,
                        execution_client=execution_client,
                    )
                )
            result["status"] = "closed" if all(item.get("status") == "submitted" for item in close_results) else "pair_close_failed"
            result["exit_reason"] = "spread_reversion" if signal["action"] == "exit_pair" else "pair_stop_loss"
            result["combined_pnl"] = combined_pnl
            result["close_orders"] = close_results
            if cycle_logger is not None and callable(getattr(cycle_logger, "log_cycle", None)):
                result["persistence"] = cycle_logger.log_cycle(result)
            return result

        result["status"] = "skipped_existing_pair"
        result["combined_pnl"] = combined_pnl
        result["positions"] = live_positions
        return result

    if signal["action"] != "enter_pair":
        result["status"] = "logged"
        return result

    latest_prices = {
        first_symbol.upper(): float(history["first"]["closes"][-1]),
        second_symbol.upper(): float(history["second"]["closes"][-1]),
    }
    trades = [
        {
            "symbol": leg["symbol"],
            "side": leg["side"],
            "qty": qty,
            "entry_price": latest_prices[leg["symbol"]],
            "leverage": 1.0,
            "market": market_type,
        }
        for leg in signal["legs"]
    ]
    risk_checks = [
        risk_engine.evaluate_trade(trade=trade, current_positions=[], current_daily_pnl=0.0)
        for trade in trades
    ]
    result["risk_checks"] = risk_checks
    if not all(check["allowed"] for check in risk_checks):
        result["status"] = "risk_rejected"
        return result

    orders = []
    for trade in trades:
        order = await asyncio.to_thread(execution_client.place_market_order, trade)
        orders.append(order)
        if order.get("status") != "submitted":
            result["status"] = "pair_execution_failed"
            result["orders"] = orders
            return result
    result["status"] = "submitted"
    result["orders"] = orders
    if cycle_logger is not None and callable(getattr(cycle_logger, "log_cycle", None)):
        result["persistence"] = cycle_logger.log_cycle(result)
    return result


async def agent_loop(*, market_service: Any, risk_engine: Any, execution_client: Any, cycle_logger: Any | None = None) -> None:
    logger.info("Agent loop starting: interval=%ss symbols=%s", LOOP_INTERVAL_SECONDS, WATCHED_SYMBOLS)
    while not _stop_event.is_set():
        if MODE == "strategy" and get_active_strategy_id() == "pairs_trading" and len(WATCHED_SYMBOLS) >= 2:
            await run_pair_cycle(
                WATCHED_SYMBOLS[0],
                WATCHED_SYMBOLS[1],
                market_service=market_service,
                risk_engine=risk_engine,
                execution_client=execution_client,
                cycle_logger=cycle_logger,
                market_type=MARKET_TYPE,
            )
        else:
            for symbol in WATCHED_SYMBOLS:
                if _stop_event.is_set():
                    break
                await run_cycle(
                    symbol,
                    market_service=market_service,
                    risk_engine=risk_engine,
                    execution_client=execution_client,
                    cycle_logger=cycle_logger,
                    mode=MODE,
                )
        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=LOOP_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            pass
    logger.info("Agent loop stopped")


def start(*, market_service: Any, risk_engine: Any, execution_client: Any, cycle_logger: Any | None = None) -> None:
    global _loop_task
    if _loop_task is None or _loop_task.done():
        _stop_event.clear()
        _loop_task = asyncio.create_task(
            agent_loop(
                market_service=market_service,
                risk_engine=risk_engine,
                execution_client=execution_client,
                cycle_logger=cycle_logger,
            )
        )


def stop() -> None:
    _stop_event.set()


def is_running() -> bool:
    return _loop_task is not None and not _loop_task.done() and not _stop_event.is_set()
