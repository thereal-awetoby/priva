from __future__ import annotations

import asyncio
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel

from app.market_data import BitgetMarketDataService
from app.paper_execution import BitgetPaperExecutionClient
from app.performance import calculate_unrealized_pnl
from app.risk_engine import RiskEngine
from app.strategy import STRATEGIES, activate_strategy as set_active_strategy, build_signal_from_ticker, get_active_strategy_id
from app import agent_loop
from app.supabase_logging import SupabaseCycleLogger

app = FastAPI(
    title="Priva Backend",
    description="Builder B backend scaffolding for Priva trading agent",
    version="0.1.0",
)

market_service = BitgetMarketDataService()
risk_engine = RiskEngine()
paper_execution_client = BitgetPaperExecutionClient()
cycle_logger = SupabaseCycleLogger()


def process_market_cycle(
    symbol: str,
    *,
    market_service: Any,
    risk_engine: RiskEngine,
) -> dict[str, Any]:
    ticker = market_service.fetch_spot_ticker(symbol)
    decision = build_signal_from_ticker(ticker)
    decision["symbol"] = symbol.upper()
    decision["market_status"] = ticker.get("status", "unknown")

    if ticker.get("status") != "live":
        log_entry = {
            "id": f"market_{symbol.lower()}_{int(__import__('time').time())}",
            "type": "market_data",
            "symbol": symbol.upper(),
            "status": "fallback",
            "reason": ticker.get("error", "network unavailable"),
        }
        return {"decision": decision, "ticker": ticker, "risk_check": {"allowed": False, "reasons": ["market_fallback"]}, "log_entry": log_entry}

    trade = {
        "symbol": symbol.upper(),
        "side": "buy" if decision["action"] == "buy" else "sell",
        "qty": float(decision.get("size", 0) or 0),
        "entry_price": float(ticker.get("last_price", 0.0) or 0.0),
        "leverage": float(decision.get("leverage", 1.0) or 1.0),
    }

    risk_check = risk_engine.evaluate_trade(
        trade=trade,
        current_positions=[],
        current_daily_pnl=0.0,
    )

    log_entry = {
        "id": f"trade_{symbol.lower()}_{int(__import__('time').time())}",
        "type": "trade",
        "symbol": symbol.upper(),
        "action": trade["side"],
        "status": "accepted" if risk_check["allowed"] else "rejected",
        "reason": "risk check passed" if risk_check["allowed"] else risk_check["reasons"],
    }

    return {
        "decision": decision,
        "ticker": ticker,
        "risk_check": risk_check,
        "log_entry": log_entry,
    }


class KillSwitchRequest(BaseModel):
    enabled: bool


class TradeRequest(BaseModel):
    symbol: str
    side: str
    qty: float
    entry_price: float
    leverage: float = 1.0
    market: Literal["spot", "futures"] = "futures"


class ClosePositionRequest(BaseModel):
    position_side: Literal["buy", "sell"]
    qty: float | None = None


@app.get("/market-data")
def market_data(symbol: str = "AAPLUSDT") -> dict[str, Any]:
    snapshot = market_service.get_market_snapshot(symbol)
    return snapshot


@app.get("/fetch-data")
def fetch_data(symbol: str = "AAPLUSDT") -> dict[str, Any]:
    snapshot = market_service.get_market_snapshot(symbol)
    return snapshot


@app.get("/agent-cycle")
def agent_cycle(symbol: str = "AAPLUSDT") -> dict[str, Any]:
    result = process_market_cycle(symbol, market_service=market_service, risk_engine=risk_engine)
    return result


@app.get("/agent-loop")
def agent_loop_status() -> dict[str, Any]:
    return {
        "running": agent_loop.is_running(),
        "interval_seconds": agent_loop.LOOP_INTERVAL_SECONDS,
        "watched_symbols": agent_loop.WATCHED_SYMBOLS,
        "recent_cycles": agent_loop.recent_cycles(),
    }


@app.get("/debug/bitget-account")
def debug_bitget_account(symbol: str = "AAPLUSDT") -> dict[str, Any]:
    return paper_execution_client.fetch_account_mode(symbol)


async def periodic_market_loop() -> None:
    while True:
        ticker = market_service.fetch_spot_ticker("AAPLUSDT")
        if ticker.get("status") == "live":
            print(f"[market-loop] AAPLUSDT={ticker.get('last_price')} | ts={ticker.get('timestamp_iso')}")
        else:
            print(f"[market-loop] AAPLUSDT fallback: {ticker.get('error')}")
        app.state.last_market_snapshot = ticker
        await asyncio.sleep(60)


@app.on_event("startup")
async def startup_event() -> None:
    persisted_strategy = cycle_logger.fetch_active_strategy()
    if persisted_strategy:
        set_active_strategy(persisted_strategy)
    agent_loop.start(
        market_service=market_service,
        risk_engine=risk_engine,
        execution_client=paper_execution_client,
        cycle_logger=cycle_logger,
    )


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "priva-backend",
        "paper_trading": True,
        "kill_switch_active": False,
        "timestamp": "2026-09-10T00:00:00Z",
    }


@app.get("/status")
def status() -> dict[str, Any]:
    return {
        "mode": "autonomous",
        "agent_state": "online",
        "paper_trading": True,
        "risk_engine": "armed",
        "last_cycle": "2026-09-10T00:00:00Z",
        "next_cycle": "2026-09-10T00:05:00Z",
    }


@app.get("/positions")
def positions() -> dict[str, Any]:
    exchange_positions = paper_execution_client.fetch_futures_positions()
    if exchange_positions["status"] == "ok":
        live_positions = []
        for position in exchange_positions["positions"]:
            qty = float(position.get("total", position.get("available", 0)) or 0)
            if qty <= 0:
                continue
            side = "buy" if position.get("holdSide") == "long" else "sell"
            entry_price = float(
                position.get(
                    "openPriceAvg",
                    position.get(
                        "averageOpenPrice",
                        position.get("openAvgPrice", position.get("openPrice", 0)),
                    ),
                )
                or 0
            )
            mark_price = float(position.get("markPrice", 0) or 0)
            notional = abs(float(position.get("openCost", 0) or 0))
            if notional <= 0:
                notional = entry_price * qty if entry_price > 0 else mark_price * qty
            live_positions.append(
                {
                    "symbol": position.get("symbol"),
                    "side": side,
                    "qty": qty,
                    "entry_price": entry_price,
                    "mark_price": mark_price,
                    "notional_usd": notional,
                    "unrealized_pnl": float(position.get("unrealizedPL", 0) or 0),
                    "leverage": float(position.get("leverage", 1) or 1),
                    "margin_mode": position.get("marginMode"),
                    "source": "bitget_paper",
                }
            )
        return {"positions": live_positions, "total_positions": len(live_positions)}

    cycles = cycle_logger.fetch_cycles()
    if cycles:
        live_positions = calculate_unrealized_pnl(
            cycles,
            mark_fetcher=market_service.fetch_spot_ticker,
        )["open_positions"]
        if live_positions:
            for position in live_positions:
                position["leverage"] = 1.0
                position["source"] = "paper"
            return {"positions": live_positions, "total_positions": len(live_positions)}

    position_map: dict[tuple[str, str], dict[str, Any]] = {}
    for cycle in reversed(cycles):
        order = cycle.get("order_result") or {}
        exchange_data = order.get("exchange", {}).get("data") or {}
        if cycle.get("status") != "submitted" or not exchange_data.get("orderId"):
            continue
        ticker = cycle.get("ticker") or {}
        risk = cycle.get("risk_check", {}).get("risk", {})
        symbol = str(cycle.get("symbol", ""))
        side = str(cycle.get("decision", {}).get("action", ""))
        entry_price = float(ticker.get("last_price", 0) or 0)
        notional = float(risk.get("notional", 0) or 0)
        qty = notional / max(entry_price, 1)
        key = (symbol, side)
        position = position_map.setdefault(
            key,
            {"symbol": symbol, "side": side, "qty": 0.0, "notional_usd": 0.0, "leverage": risk.get("leverage", 1), "source": "paper", "order_ids": []},
        )
        position["qty"] += qty
        position["notional_usd"] += notional
        position["entry_price"] = position["notional_usd"] / position["qty"]
        position["mark_price"] = ticker.get("last_price", 0)
        position["order_ids"].append(exchange_data.get("orderId"))
    live_positions = list(position_map.values())
    if live_positions:
        return {"positions": live_positions, "total_positions": len(live_positions)}

    return {
        "positions": [
            {
                "symbol": "AAPL",
                "side": "long",
                "qty": 14,
                "entry_price": 220.65,
                "mark_price": 223.12,
                "notional_usd": 3123.68,
                "leverage": 1.5,
                "source": "paper",
            },
            {
                "symbol": "NVDA",
                "side": "short",
                "qty": 8,
                "entry_price": 129.4,
                "mark_price": 123.9,
                "notional_usd": 991.2,
                "leverage": 2.0,
                "source": "paper",
            },
        ],
        "total_positions": 2,
    }


@app.post("/positions/{symbol}/close")
def close_position(symbol: str, payload: ClosePositionRequest) -> dict[str, Any]:
    current = next(
        (
            position
            for position in positions()["positions"]
            if position.get("symbol") == symbol.upper()
            and position.get("side") == payload.position_side
        ),
        None,
    )
    if current is None:
        return {"status": "rejected", "message": "position not found"}

    qty = payload.qty if payload.qty is not None else float(current["qty"])
    if qty <= 0 or qty > float(current["qty"]):
        return {"status": "rejected", "message": "close quantity exceeds open position"}

    if qty != float(current["qty"]):
        return {
            "status": "rejected",
            "message": "Partial close not currently supported - close the full position instead.",
        }

    execution = paper_execution_client.flash_close_position(symbol, payload.position_side)
    if execution.get("status") != "submitted":
        return {
            "order": {"symbol": symbol.upper(), "position_side": payload.position_side, "qty": qty},
            **execution,
        }

    execution["closed_position_side"] = payload.position_side
    order = {"symbol": symbol.upper(), "position_side": payload.position_side, "qty": qty}
    mark_price = float(current.get("mark_price", current.get("entry_price", 0)))
    execution["trade_side"] = "close"
    execution["qty"] = qty
    execution["entry_price"] = mark_price
    cycle_logger.log_cycle(
        {
            "symbol": symbol.upper(),
            "status": "closed",
            "decision": {"action": "close", "closed_position_side": payload.position_side},
            "ticker": market_service.fetch_spot_ticker(symbol),
            "risk_check": {"allowed": True, "risk": {"notional": qty * mark_price}},
            "order": execution,
        }
    )

    return {
        "status": "submitted",
        "order": order,
        "closed_position_side": payload.position_side,
        "risk": {"notional": qty * mark_price},
        **execution,
    }


@app.get("/pnl")
def pnl() -> dict[str, Any]:
    cycles = cycle_logger.fetch_cycles(session_id=cycle_logger.session_id)
    logged_pnl = calculate_unrealized_pnl(
        cycles,
        mark_fetcher=market_service.fetch_spot_ticker,
    ) if cycles else {"realized_pnl": 0.0}
    live_positions = positions()["positions"]
    unrealized_pnl = round(
        sum(float(position.get("unrealized_pnl", 0) or 0) for position in live_positions),
        4,
    )
    realized_pnl = round(float(logged_pnl.get("realized_pnl", 0) or 0), 4)
    total_pnl = round(realized_pnl + unrealized_pnl, 4)
    return {
        "unrealized_pnl": unrealized_pnl,
        "realized_pnl": realized_pnl,
        "daily_pnl": total_pnl,
        "total_pnl": total_pnl,
        "currency": "USD",
        "source": "bitget_and_supabase",
        "session_id": cycle_logger.session_id,
        "open_positions": live_positions,
    }


@app.get("/risk-usage")
def risk_usage() -> dict[str, Any]:
    live_positions = positions()["positions"]
    position_size = round(
        sum(float(position.get("notional_usd", 0) or 0) for position in live_positions),
        4,
    )
    current_leverage = max(
        (float(position.get("leverage", 0) or 0) for position in live_positions),
        default=0.0,
    )
    current_daily_loss = max(0.0, -float(pnl()["daily_pnl"]))
    max_position_size = float(risk_engine.max_position_size)
    max_daily_loss = float(risk_engine.max_daily_loss)
    max_leverage = float(risk_engine.max_leverage)
    return {
        "max_position_size": max_position_size,
        "current_position_size": position_size,
        "max_daily_loss": max_daily_loss,
        "current_daily_loss": round(current_daily_loss, 4),
        "max_leverage": max_leverage,
        "current_leverage": current_leverage,
        "usage_percent": {
            "position_size": round(position_size / max_position_size * 100, 2) if max_position_size else 0.0,
            "daily_loss": round(current_daily_loss / max_daily_loss * 100, 2) if max_daily_loss else 0.0,
            "leverage": round(current_leverage / max_leverage * 100, 2) if max_leverage else 0.0,
        },
        "positions": live_positions,
        "source": "bitget_and_supabase",
    }


@app.get("/activity-log")
def activity_log() -> dict[str, Any]:
    cycles = cycle_logger.fetch_cycles()
    if cycles:
        return {
            "entries": [
                {
                    "id": (cycle.get("order_result") or {}).get("order_id") or f"cycle_{cycle.get('created_at', '')}",
                    "type": "trade" if cycle.get("order_result") else "agent_cycle",
                    "symbol": cycle.get("symbol"),
                    "action": (cycle.get("decision") or {}).get("action"),
                    "status": cycle.get("status"),
                    "risk_check": cycle.get("risk_check"),
                    "intent_hash": (cycle.get("intent") or {}).get("intent_hash"),
                    "timestamp": cycle.get("created_at"),
                }
                for cycle in cycles
            ]
        }

    return {
        "entries": [
            {
                "id": "evt_001",
                "type": "trade",
                "symbol": "AAPL",
                "action": "buy",
                "amount_usd": 2100,
                "status": "filled",
                "timestamp": "2026-09-10T00:00:20Z",
            },
            {
                "id": "evt_002",
                "type": "risk_check",
                "symbol": "NVDA",
                "result": "approved",
                "reason": "within max leverage",
                "timestamp": "2026-09-10T00:02:10Z",
            },
            {
                "id": "evt_003",
                "type": "intent",
                "symbol": "MSFT",
                "status": "encrypted",
                "timestamp": "2026-09-10T00:03:00Z",
            },
        ]
    }


@app.get("/strategies")
def strategies() -> dict[str, Any]:
    return {
        "strategies": [
            {
                "id": "momentum_breakout",
                "name": "Momentum Breakout",
                "type": "playbook",
                "status": "active" if get_active_strategy_id() == "momentum_breakout" else "inactive",
                "description": "Long when trend and volume accelerate above baseline.",
            },
            {
                "id": "mean_reversion",
                "name": "Mean Reversion",
                "type": "prebuilt",
                "status": "active" if get_active_strategy_id() == "mean_reversion" else "inactive",
                "description": "Fade moves that extend at least 1% away from the opening price.",
            },
        ]
    }


@app.post("/strategies/{strategy_id}/activate")
def activate_strategy(strategy_id: str) -> dict[str, Any]:
    if not set_active_strategy(strategy_id):
        return {"strategy_id": strategy_id, "status": "rejected", "message": "unknown strategy"}
    persistence = cycle_logger.save_active_strategy(strategy_id)
    if cycle_logger.configured and persistence["status"] != "saved":
        return {"strategy_id": strategy_id, "status": "rejected", "message": "strategy could not be persisted"}
    return {
        "strategy_id": strategy_id,
        "status": "activated",
        "mode": "strategy",
        "active": True,
        "persistence": persistence["status"],
    }


@app.get("/kill-switch")
def get_kill_switch() -> dict[str, Any]:
    return {"enabled": False, "message": "Agent loop is active."}


@app.post("/kill-switch")
async def set_kill_switch(payload: KillSwitchRequest) -> dict[str, Any]:
    if payload.enabled:
        agent_loop.stop()
    else:
        agent_loop.start(
            market_service=market_service,
            risk_engine=risk_engine,
            execution_client=paper_execution_client,
            cycle_logger=cycle_logger,
        )
    return {
        "enabled": payload.enabled,
        "running": agent_loop.is_running(),
        "message": "Kill switch updated." if payload.enabled else "Agent loop restarted.",
    }


@app.post("/risk-check")
def risk_check(payload: dict[str, Any]) -> dict[str, Any]:
    trade = payload.get("trade", {})
    current_positions = payload.get("current_positions", [])
    current_daily_pnl = float(payload.get("current_daily_pnl", 0.0))
    result = risk_engine.evaluate_trade(
        trade=trade,
        current_positions=current_positions,
        current_daily_pnl=current_daily_pnl,
    )
    return result


@app.post("/paper-trade")
def paper_trade(payload: TradeRequest) -> dict[str, Any]:
    order = payload.model_dump()
    result = risk_engine.evaluate_trade(
        trade=order,
        current_positions=[],
        current_daily_pnl=0.0,
    )

    if not result["allowed"]:
        return {
            "status": "rejected",
            "order": order,
            "reasons": result["reasons"],
            "risk": result["risk"],
        }

    execution = paper_execution_client.place_market_order(order)
    return {"order": order, "risk": result["risk"], **execution}


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Priva backend is live."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
