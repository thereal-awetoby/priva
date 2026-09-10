from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

from app.strategy import build_signal_from_ticker

logger = logging.getLogger("priva.agent_loop")
LOOP_INTERVAL_SECONDS = int(os.getenv("AGENT_LOOP_INTERVAL_SECONDS", "300"))
WATCHED_SYMBOLS = [
    symbol.strip()
    for symbol in os.getenv("AGENT_WATCHED_SYMBOLS", "AAPLUSDT,TSLAUSDT,MSFTUSDT").split(",")
    if symbol.strip()
]
ORDER_QTY = float(os.getenv("AGENT_ORDER_QTY", "1"))

_loop_task: asyncio.Task | None = None
_stop_event = asyncio.Event()
_recent_cycles: list[dict[str, Any]] = []


def _record_cycle(entry: dict[str, Any]) -> None:
    _recent_cycles.append(entry)
    del _recent_cycles[:-100]


def recent_cycles() -> list[dict[str, Any]]:
    return list(_recent_cycles)


def build_encrypted_intent(symbol: str, decision: dict[str, Any], risk_result: dict[str, Any]) -> dict[str, Any]:
    intent = {
        "symbol": symbol.upper(),
        "action": decision["action"],
        "signal_strength": decision["signal_strength"],
        "risk_notional": risk_result["risk"].get("notional", 0.0),
    }
    serialized = json.dumps(intent, sort_keys=True, separators=(",", ":")).encode()
    return {"intent_hash": hashlib.sha256(serialized).hexdigest(), "intent": intent}


async def run_cycle(symbol: str, *, market_service: Any, risk_engine: Any, execution_client: Any) -> dict[str, Any]:
    cycle_start = datetime.now(timezone.utc)
    try:
        ticker = await asyncio.to_thread(market_service.fetch_spot_ticker, symbol)
        decision = build_signal_from_ticker(ticker)
        decision.update({"symbol": symbol.upper(), "market_status": ticker.get("status", "unknown")})

        if ticker.get("status") != "live" or decision["action"] == "hold":
            result = {
                "status": "logged",
                "symbol": symbol.upper(),
                "decision": decision,
                "ticker": ticker,
                "risk_check": {"allowed": False, "reasons": ["no_trade_signal"]},
                "order": None,
            }
            _record_cycle(result)
            return result

        trade = {
            "symbol": symbol.upper(),
            "side": decision["action"],
            "qty": ORDER_QTY,
            "entry_price": float(ticker.get("last_price", 0.0) or 0.0),
            "leverage": 1.0,
            "market": "futures",
        }
        risk_result = risk_engine.evaluate_trade(
            trade=trade,
            current_positions=[],
            current_daily_pnl=0.0,
        )
        if not risk_result["allowed"]:
            result = {"status": "risk_rejected", "symbol": symbol.upper(), "decision": decision, "risk_check": risk_result, "order": None}
            _record_cycle(result)
            return result

        intent = build_encrypted_intent(symbol, decision, risk_result)
        order_result = await asyncio.to_thread(execution_client.place_market_order, trade)
        result = {
            "status": order_result.get("status", "unknown"),
            "symbol": symbol.upper(),
            "decision": decision,
            "ticker": ticker,
            "risk_check": risk_result,
            "intent": intent,
            "order": order_result,
            "duration_seconds": round((datetime.now(timezone.utc) - cycle_start).total_seconds(), 3),
        }
        _record_cycle(result)
        return result
    except Exception as exc:
        logger.exception("[%s] cycle failed: %s", symbol, exc)
        result = {"status": "error", "symbol": symbol.upper(), "error": str(exc)}
        _record_cycle(result)
        return result


async def agent_loop(*, market_service: Any, risk_engine: Any, execution_client: Any) -> None:
    logger.info("Agent loop starting: interval=%ss symbols=%s", LOOP_INTERVAL_SECONDS, WATCHED_SYMBOLS)
    while not _stop_event.is_set():
        for symbol in WATCHED_SYMBOLS:
            if _stop_event.is_set():
                break
            await run_cycle(symbol, market_service=market_service, risk_engine=risk_engine, execution_client=execution_client)
        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=LOOP_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            pass
    logger.info("Agent loop stopped")


def start(*, market_service: Any, risk_engine: Any, execution_client: Any) -> None:
    global _loop_task
    if _loop_task is None or _loop_task.done():
        _stop_event.clear()
        _loop_task = asyncio.create_task(
            agent_loop(market_service=market_service, risk_engine=risk_engine, execution_client=execution_client)
        )


def stop() -> None:
    _stop_event.set()


def is_running() -> bool:
    return _loop_task is not None and not _loop_task.done() and not _stop_event.is_set()
