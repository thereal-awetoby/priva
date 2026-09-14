from __future__ import annotations

import asyncio
from typing import Any, Literal

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.market_data import BitgetMarketDataService
from app.paper_execution import BitgetPaperExecutionClient
from app.performance import calculate_unrealized_pnl
from app.risk_engine import RiskEngine
from app.strategy import (
    STRATEGIES,
    STRATEGY_CATALOG,
    activate_strategy as set_active_strategy,
    backtest_strategy,
    build_signal_from_ticker,
    configure_builtin_strategy,
    get_active_strategy_id,
    configure_symbol_strategies,
    get_strategy_for_symbol,
    list_strategy_catalog,
    parse_natural_language_strategy,
    parse_structured_strategy,
    register_custom_strategy,
)
from app import agent_loop
from app.supabase_logging import SupabaseCycleLogger
from app.auth import AuthenticatedUser, credential_vault, current_user, supabase_auth
from app.user_runtime import user_runtime_registry

app = FastAPI(
    title="Priva Backend",
    description="Builder B backend scaffolding for Priva trading agent",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

market_service = BitgetMarketDataService()
risk_engine = RiskEngine()
paper_execution_client = BitgetPaperExecutionClient()
cycle_logger = SupabaseCycleLogger()


def execution_client_for(user: AuthenticatedUser) -> BitgetPaperExecutionClient:
    credentials = credential_vault.get(user.id)
    if credentials is None and credential_vault.configured:
        encrypted = cycle_logger.fetch_user_credentials(user.id)
        if encrypted and credential_vault.import_encrypted(user.id, encrypted):
            credentials = credential_vault.get(user.id)
    if credentials:
        client = BitgetPaperExecutionClient(session=paper_execution_client.session)
        client.configure_credentials(
            credentials["api_key"], credentials["api_secret"], credentials["passphrase"]
        )
        return client
    if user.id == "local-development" and not supabase_auth.required:
        return paper_execution_client
    return BitgetPaperExecutionClient(session=paper_execution_client.session)


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


class IntentEvaluationRequest(BaseModel):
    strategy_id: str | None = None
    symbol: str
    side: Literal["buy", "sell"]
    qty: float
    entry_price: float
    leverage: float = 1.0
    current_positions: list[dict[str, Any]] | None = None
    current_daily_pnl: float = 0.0


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


class StrategyActivationRequest(BaseModel):
    symbols: list[str] | None = None
    strategy_by_symbol: dict[str, str] | None = None


class AgentSettingsRequest(BaseModel):
    market: Literal["spot", "futures"]
    take_profit_pct: float | None = None
    stop_loss_pct: float | None = None
    close_on_signal_violation: bool | None = None


class UserAgentSettingsRequest(BaseModel):
    market: Literal["spot", "futures"] = "futures"
    take_profit_pct: float = 5
    stop_loss_pct: float = 2
    close_on_signal_violation: bool = True
    symbols: list[str] | None = None
    strategy_id: str | None = None
    strategy_by_symbol: dict[str, str] | None = None
    max_position_size: float = 25000
    max_daily_loss: float = 1500
    max_leverage: float = 5
    risk_enabled: bool = True
    allowed_symbols: list[str] | None = None


class BitgetConnectionRequest(BaseModel):
    api_key: str
    api_secret: str
    passphrase: str
    symbol: str = "AAPLUSDT"


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
        "market": agent_loop.MARKET_TYPE,
        "strategy_by_symbol": {symbol: get_strategy_for_symbol(symbol) for symbol in agent_loop.WATCHED_SYMBOLS},
        "recent_cycles": agent_loop.recent_cycles(),
    }


@app.get("/agent-settings")
def agent_settings() -> dict[str, Any]:
    return {"status": "ok", "market": agent_loop.MARKET_TYPE, **agent_loop.get_exit_rules()}


@app.post("/agent-settings")
def update_agent_settings(payload: AgentSettingsRequest) -> dict[str, Any]:
    try:
        settings = agent_loop.configure_exit_rules(
            take_profit_pct=payload.take_profit_pct,
            stop_loss_pct=payload.stop_loss_pct,
            close_on_signal_violation=payload.close_on_signal_violation,
        )
        return {"status": "updated", "market": agent_loop.configure_market_type(payload.market), **settings}
    except ValueError as exc:
        return {"status": "rejected", "message": str(exc)}


@app.get("/debug/bitget-account")
def debug_bitget_account(symbol: str = "AAPLUSDT", user: AuthenticatedUser = Depends(current_user)) -> dict[str, Any]:
    client = execution_client_for(user)
    return client.fetch_account_mode(symbol)


@app.get("/user/agent-loop")
def user_agent_loop_status(user: AuthenticatedUser = Depends(current_user)) -> dict[str, Any]:
    return user_runtime_registry.status(user.id)


@app.get("/user/agent-settings")
def user_agent_settings(user: AuthenticatedUser = Depends(current_user)) -> dict[str, Any]:
    runtime = user_runtime_registry.get(user.id)
    if runtime:
        return {"status": "ok", **user_runtime_registry.status(user.id)}
    return {"status": "ok", **SupabaseCycleLogger(user_id=user.id).fetch_user_settings(user.id)}


@app.post("/user/agent-settings")
def update_user_agent_settings(payload: UserAgentSettingsRequest, user: AuthenticatedUser = Depends(current_user)) -> dict[str, Any]:
    settings = payload.model_dump()
    if settings["strategy_id"] and settings["strategy_id"] not in STRATEGIES:
        return {"status": "rejected", "message": "unknown strategy"}
    settings["symbols"] = [str(symbol).upper() for symbol in (settings["symbols"] or ["AAPLUSDT", "TSLAUSDT"])]
    logger = SupabaseCycleLogger(user_id=user.id)
    persistence = logger.save_user_settings(user.id, settings)
    if logger.configured and persistence["status"] != "saved":
        return {"status": "rejected", "message": "user settings could not be persisted"}
    runtime = user_runtime_registry.get(user.id)
    if runtime:
        runtime.market_type = settings["market"]
        runtime.symbols = settings["symbols"]
        runtime.strategy_id = settings["strategy_id"] or runtime.strategy_id
        runtime.strategy_by_symbol = settings["strategy_by_symbol"] or {}
        runtime.take_profit_pct = settings["take_profit_pct"]
        runtime.stop_loss_pct = settings["stop_loss_pct"]
        runtime.close_on_signal_violation = settings["close_on_signal_violation"]
        runtime.risk_engine.update_settings({
            "max_position_size": settings["max_position_size"],
            "max_daily_loss": settings["max_daily_loss"],
            "max_leverage": settings["max_leverage"],
            "enabled": settings["risk_enabled"],
            "allowed_symbols": settings["allowed_symbols"] or [],
        })
    return {"status": "updated", **settings, "persistence": persistence["status"]}


@app.post("/connection/bitget")
def connect_bitget(payload: BitgetConnectionRequest, user: AuthenticatedUser = Depends(current_user)) -> dict[str, Any]:
    values = (payload.api_key.strip(), payload.api_secret.strip(), payload.passphrase.strip())
    if not all(values):
        return {"status": "rejected", "message": "All Bitget credential fields are required"}

    candidate = BitgetPaperExecutionClient(session=paper_execution_client.session)
    candidate.configure_credentials(*values)
    verification = candidate.fetch_account_mode(payload.symbol)
    if verification.get("status") != "ok":
        return {
            "status": "rejected",
            "message": verification.get("message", "Bitget credentials could not be verified"),
        }

    if credential_vault.configured:
        credential_vault.put(user.id, {"api_key": values[0], "api_secret": values[1], "passphrase": values[2]})
        persistence = cycle_logger.save_user_credentials(user.id, credential_vault.export(user.id) or "")
        if cycle_logger.configured and persistence["status"] != "saved":
            credential_vault.delete(user.id)
            return {"status": "rejected", "message": "Credentials could not be persisted securely"}
    elif user.id == "local-development" and not supabase_auth.required:
        paper_execution_client.configure_credentials(*values)
    else:
        return {"status": "rejected", "message": "PRIVA_CREDENTIAL_ENCRYPTION_KEY is not configured"}
    runtime = user_runtime_registry.start(user.id, execution_client_for(user)) if supabase_auth.required else None
    return {
        "status": "connected",
        "symbol": payload.symbol.upper(),
        "position_mode": verification.get("position_mode"),
        "credentials_stored": "memory_only",
        "worker": user_runtime_registry.status(user.id) if runtime else {"running": False},
    }


@app.post("/connection/bitget/disconnect")
async def disconnect_bitget(user: AuthenticatedUser = Depends(current_user)) -> dict[str, Any]:
    await user_runtime_registry.stop(user.id)
    credential_vault.delete(user.id)
    cycle_logger.delete_user_credentials(user.id)
    if user.id == "local-development":
        paper_execution_client.clear_credentials()
    return {"status": "disconnected"}


@app.get("/auth/session")
def auth_session(user: AuthenticatedUser = Depends(current_user)) -> dict[str, Any]:
    return {"status": "authenticated", "user_id": user.id, "email": user.email}


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
    if supabase_auth.required:
        for record in cycle_logger.fetch_connected_users():
            user_id = str(record.get("user_id", ""))
            encrypted = record.get("encrypted_credentials")
            if user_id and encrypted and credential_vault.import_encrypted(user_id, encrypted):
                user = AuthenticatedUser(user_id)
                user_runtime_registry.start(user_id, execution_client_for(user))
        return
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
    trade_metrics = _trade_metrics(cycles)
    return {
        "unrealized_pnl": unrealized_pnl,
        "realized_pnl": realized_pnl,
        "daily_pnl": total_pnl,
        "total_pnl": total_pnl,
        "win_rate_pct": trade_metrics["win_rate_pct"],
        "max_drawdown_pct": trade_metrics["max_drawdown_pct"],
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
        "allowed_symbols": list(risk_engine.allowed_symbols) if risk_engine.allowed_symbols else [],
        "positions": live_positions,
        "source": "bitget_and_supabase",
    }


@app.get("/risk-settings")
def risk_settings() -> dict[str, Any]:
    return {"status": "ok", **risk_engine.get_settings()}


@app.post("/risk-settings")
def update_risk_settings(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if payload is None or not isinstance(payload, dict):
        return {"status": "rejected", "message": "payload must be an object"}

    try:
        settings = risk_engine.update_settings(payload)
        return {"status": "updated", **settings}
    except ValueError as exc:
        return {"status": "rejected", "message": str(exc)}


@app.get("/activity-log")
def activity_log() -> dict[str, Any]:
    cycles = cycle_logger.fetch_cycles()
    if not cycles:
        cycles = agent_loop.recent_cycles()
    if cycles:
        return {
            "entries": [
                {
                    "id": ((cycle.get("order_result") or cycle.get("order") or {}).get("order_id") or f"cycle_{cycle.get('created_at', '')}"),
                    "type": "trade" if (cycle.get("order_result") or cycle.get("order")) else "agent_cycle",
                    "symbol": cycle.get("symbol"),
                    "action": (cycle.get("decision") or {}).get("action"),
                    "status": cycle.get("status"),
                    "risk_check": cycle.get("risk_check"),
                    "intent_hash": (cycle.get("intent") or {}).get("intent_hash"),
                    "mode": cycle.get("mode", "autonomous"),
                    "timestamp": cycle.get("created_at"),
                    "opened_at": cycle.get("created_at") if (cycle.get("order_result") or cycle.get("order")) else None,
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
                "mode": "autonomous",
                "timestamp": "2026-09-10T00:00:20Z",
                "opened_at": "2026-09-10T00:00:20Z",
            },
            {
                "id": "evt_002",
                "type": "risk_check",
                "symbol": "NVDA",
                "result": "approved",
                "reason": "within max leverage",
                "mode": "strategy",
                "timestamp": "2026-09-10T00:02:10Z",
            },
            {
                "id": "evt_003",
                "type": "intent",
                "symbol": "MSFT",
                "status": "encrypted",
                "mode": "autonomous",
                "timestamp": "2026-09-10T00:03:00Z",
            },
        ]
    }


@app.get("/strategies")
def strategies() -> dict[str, Any]:
    catalog = []
    for strategy_id, definition in list_strategy_catalog().items():
        catalog.append(
            {
                **definition,
                "status": "active" if get_active_strategy_id() == strategy_id else "inactive",
            }
        )
    return {"strategies": catalog}


@app.post("/strategies/{strategy_id}/activate")
def activate_strategy(strategy_id: str, payload: StrategyActivationRequest | None = None, user: AuthenticatedUser = Depends(current_user)) -> dict[str, Any]:
    symbols = None
    strategy_map = payload.strategy_by_symbol if payload is not None else None
    if strategy_id not in STRATEGIES:
        return {"strategy_id": strategy_id, "status": "rejected", "message": "unknown strategy"}
    if payload is not None and payload.symbols is not None:
        symbols = list(dict.fromkeys(symbol.upper() for symbol in payload.symbols))
        unsupported = [symbol for symbol in symbols if symbol not in {"AAPLUSDT", "TSLAUSDT"}]
        if not symbols or unsupported:
            return {
                "strategy_id": strategy_id,
                "status": "rejected",
                "message": "symbols must include AAPLUSDT and/or TSLAUSDT only",
            }

    if supabase_auth.required:
        normalized_map = {}
        for symbol, mapped_strategy in (strategy_map or {}).items():
            normalized_symbol = str(symbol).strip().upper()
            if normalized_symbol not in {"AAPLUSDT", "TSLAUSDT"} or mapped_strategy not in STRATEGIES:
                return {"strategy_id": strategy_id, "status": "rejected", "message": "invalid per-symbol strategy assignment"}
            normalized_map[normalized_symbol] = mapped_strategy
        settings: dict[str, Any] = {"strategy_id": strategy_id}
        if symbols is not None:
            settings["symbols"] = symbols
        if normalized_map:
            settings["strategy_by_symbol"] = normalized_map
        logger = SupabaseCycleLogger(user_id=user.id)
        persistence = logger.save_user_settings(user.id, settings)
        if logger.configured and persistence["status"] != "saved":
            return {"strategy_id": strategy_id, "status": "rejected", "message": "strategy could not be persisted"}
        runtime = user_runtime_registry.get(user.id)
        if runtime:
            runtime.strategy_id = strategy_id
            if symbols is not None:
                runtime.symbols = symbols
            if normalized_map:
                runtime.strategy_by_symbol = normalized_map
        return {
            "strategy_id": strategy_id,
            "status": "activated",
            "mode": "strategy",
            "active": True,
            "symbols": runtime.symbols if runtime else symbols or [],
            "strategy_by_symbol": runtime.strategy_by_symbol if runtime else normalized_map,
            "persistence": persistence["status"],
        }

    if strategy_map is not None:
        unsupported_map_symbols = [symbol.upper() for symbol in strategy_map if symbol.upper() not in {"AAPLUSDT", "TSLAUSDT"}]
        if unsupported_map_symbols:
            return {
                "strategy_id": strategy_id,
                "status": "rejected",
                "message": "strategy_by_symbol supports AAPLUSDT and TSLAUSDT only",
            }
        try:
            normalized_map = configure_symbol_strategies(strategy_map)
        except ValueError as exc:
            return {"strategy_id": strategy_id, "status": "rejected", "message": str(exc)}
        if symbols is None:
            symbols = list(normalized_map)

    set_active_strategy(strategy_id)

    if symbols is not None:
        agent_loop.configure_watched_symbols(symbols)

    persistence = cycle_logger.save_active_strategy(strategy_id)
    if cycle_logger.configured and persistence["status"] != "saved":
        return {"strategy_id": strategy_id, "status": "rejected", "message": "strategy could not be persisted"}
    return {
        "strategy_id": strategy_id,
        "status": "activated",
        "mode": "strategy",
        "active": True,
        "symbols": agent_loop.WATCHED_SYMBOLS,
        "strategy_by_symbol": {symbol: get_strategy_for_symbol(symbol) for symbol in agent_loop.WATCHED_SYMBOLS},
        "persistence": persistence["status"],
    }


@app.post("/strategies/{strategy_id}/backtest")
def backtest_strategy_endpoint(strategy_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    if strategy_id not in STRATEGIES:
        return {"strategy_id": strategy_id, "status": "rejected", "message": "unknown strategy"}

    candles = payload.get("candles", [])
    if candles is None or not isinstance(candles, list):
        return {"strategy_id": strategy_id, "status": "rejected", "message": "candles must be a list"}

    try:
        initial_capital = float(payload.get("initial_capital", 10000.0))
        return backtest_strategy(strategy_id, candles, initial_capital=initial_capital)
    except ValueError as exc:
        return {"strategy_id": strategy_id, "status": "rejected", "message": str(exc)}


@app.post("/strategies/parse")
def parse_strategy(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"status": "rejected", "message": "payload must be an object"}

    has_text = "text" in payload
    has_strategy = "strategy" in payload

    if has_text and has_strategy:
        return {"status": "rejected", "message": "payload must include either text or strategy, not both"}

    def _attach_metadata(response: dict[str, Any]) -> dict[str, Any]:
        name = payload.get("name")
        description = payload.get("description")

        if isinstance(name, str) and name.strip():
            response["name"] = name.strip()
        if isinstance(description, str) and description.strip():
            response["description"] = description.strip()

        return response

    if has_text:
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            return {"status": "rejected", "message": "text must be a non-empty string"}
        use_gemini = bool(payload.get("use_gemini", False) or payload.get("use_grok", False) or payload.get("use_qwen", False))
        try:
            parsed = parse_natural_language_strategy(text, use_gemini=use_gemini)
            if parsed.get("kind") == "builtin":
                config = {}
                for key, parsed_key in (
                    ("threshold_pct", "threshold_pct"),
                    ("position_size", "position_size"),
                    ("size", "position_size"),
                    ("leverage", "leverage"),
                    ("take_profit_pct", "take_profit_pct"),
                    ("take_profit", "take_profit_pct"),
                    ("stop_loss_pct", "stop_loss_pct"),
                    ("stop_loss", "stop_loss_pct"),
                ):
                    if key in payload:
                        config[parsed_key] = payload[key]
                if config:
                    configure_builtin_strategy(parsed["target_strategy"], config)
                    parsed.update(config)
            return _attach_metadata({"status": "parsed", **parsed, "strategy_id": parsed.get("target_strategy", parsed.get("strategy_id"))})
        except ValueError as exc:
            return {"status": "rejected", "message": str(exc)}

    if has_strategy:
        strategy = payload.get("strategy")
        if not isinstance(strategy, dict):
            return {"status": "rejected", "message": "strategy must be an object"}
        try:
            parsed = parse_structured_strategy(strategy)
            if parsed.get("kind") == "builtin":
                configure_builtin_strategy(parsed["target_strategy"], parsed)
                response = {"status": "parsed", **parsed, "strategy_id": parsed["target_strategy"]}
                return _attach_metadata(response)

            strategy_id = payload.get("strategy_id") or (
                f"custom_{parsed['action']}_{parsed['comparison']}_{int(parsed['threshold_pct'] * 100)}_"
                f"{str(parsed['position_size']).replace('.', '_')}"
            )
            register_custom_strategy(strategy_id, parsed)
            response = {"status": "parsed", **parsed, "strategy_id": strategy_id}
            return _attach_metadata(response)
        except ValueError as exc:
            return {"status": "rejected", "message": str(exc)}

    return {"status": "rejected", "message": "payload must include either text or strategy"}


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


def _market_provenance(symbol: str) -> dict[str, Any]:
    snapshot = market_service.get_market_snapshot(symbol)
    data = snapshot.get("data") if isinstance(snapshot.get("data"), dict) else {}
    return {
        "symbol": snapshot.get("symbol", symbol.upper()),
        "status": snapshot.get("status", data.get("status", "unknown")),
        "source": data.get("source", "bitget_public"),
        "fetched_at": snapshot.get("fetched_at"),
        "timestamp_iso": data.get("timestamp_iso"),
        "last_price": data.get("last_price"),
        "open_price": data.get("open_price"),
        "high_24h": data.get("high_24h"),
        "low_24h": data.get("low_24h"),
        "error": data.get("error"),
    }


def _position_notional(position: dict[str, Any]) -> float:
    if not isinstance(position, dict):
        return 0.0

    qty = float(position.get("qty", position.get("total", position.get("available", 0)) or 0) or 0)
    if qty <= 0:
        return 0.0

    entry_price = float(position.get("entry_price", position.get("averageOpenPrice", position.get("openPrice", 0)) or 0) or 0)
    if entry_price <= 0:
        return 0.0

    return abs(qty * entry_price)


def _usage_summary(current_positions: list[dict[str, Any]], current_daily_pnl: float) -> dict[str, Any]:
    current_position_size = round(
        sum(_position_notional(position) for position in current_positions),
        4,
    )
    current_daily_loss = max(0.0, -float(current_daily_pnl))
    max_position_size = float(risk_engine.max_position_size)
    max_daily_loss = float(risk_engine.max_daily_loss)
    position_usage_pct = round(current_position_size / max_position_size * 100, 2) if max_position_size else 0.0
    daily_loss_usage_pct = round(current_daily_loss / max_daily_loss * 100, 2) if max_daily_loss else 0.0
    return {
        "max_position_size": max_position_size,
        "current_position_size": current_position_size,
        "max_daily_loss": max_daily_loss,
        "current_daily_loss": round(current_daily_loss, 4),
        "position_usage_pct": position_usage_pct,
        "daily_loss_usage_pct": daily_loss_usage_pct,
    }


def _action_plan_from_usage(position_usage_pct: float, daily_loss_usage_pct: float) -> str:
    if position_usage_pct >= 90.0 or daily_loss_usage_pct >= 90.0:
        return "FLATTEN"
    if position_usage_pct >= 75.0 or daily_loss_usage_pct >= 75.0:
        return "TRIM"
    return "HOLD"


def _trade_metrics(cycles: list[dict[str, Any]]) -> dict[str, float]:
    if not cycles:
        return {"win_rate_pct": 0.0, "max_drawdown_pct": 0.0}

    closed_pnls: list[float] = []
    open_lots: dict[tuple[str, str], list[dict[str, float]]] = {}
    ordered_cycles = sorted(cycles, key=lambda cycle: cycle.get("created_at") or "")

    for cycle in ordered_cycles:
        status = cycle.get("status")
        symbol = str(cycle.get("symbol", ""))
        decision = cycle.get("decision") or {}

        if status == "submitted":
            side = decision.get("action")
            if side not in {"buy", "sell"}:
                continue
            ticker = cycle.get("ticker") or {}
            entry_price = float(ticker.get("last_price", 0.0) or 0.0)
            risk = cycle.get("risk_check", {}).get("risk", {})
            notional = float(risk.get("notional", 0.0) or 0.0)
            if entry_price <= 0 or notional <= 0:
                continue
            qty = notional / entry_price
            open_lots.setdefault((symbol, side), []).append({"entry_price": entry_price, "qty": qty})
            continue

        if status != "closed":
            continue

        order = cycle.get("order_result") or {}
        close_side = order.get("closed_position_side") or decision.get("closed_position_side")
        if close_side not in {"buy", "sell"}:
            continue

        qty = float(order.get("qty", 0.0) or 0.0)
        if qty <= 0:
            continue

        exit_price = float(order.get("entry_price", 0.0) or (cycle.get("ticker") or {}).get("last_price", 0.0) or 0.0)
        if exit_price <= 0:
            continue

        lots = open_lots.get((symbol, close_side), [])
        remaining = qty

        while lots and remaining > 0:
            lot = lots[0]
            closed_qty = min(remaining, lot["qty"])
            pnl = (exit_price - lot["entry_price"]) * closed_qty if close_side == "buy" else (lot["entry_price"] - exit_price) * closed_qty
            closed_pnls.append(pnl)
            remaining -= closed_qty
            lot["qty"] -= closed_qty
            if lot["qty"] <= 0:
                lots.pop(0)

    if not closed_pnls:
        return {"win_rate_pct": 0.0, "max_drawdown_pct": 0.0}

    win_rate_pct = round((sum(1 for pnl in closed_pnls if pnl > 0) / len(closed_pnls)) * 100, 2)
    max_drawdown_pct = 0.0
    return {"win_rate_pct": win_rate_pct, "max_drawdown_pct": max_drawdown_pct}


@app.post("/intent/evaluate")
def evaluate_intent(payload: IntentEvaluationRequest) -> dict[str, Any]:
    strategy_id = payload.strategy_id or get_active_strategy_id()

    if strategy_id not in STRATEGIES:
        return {
            "status": "rejected",
            "verdict": "REJECT",
            "action_plan": "REJECT",
            "strategy_id": strategy_id,
            "market_provenance": _market_provenance(payload.symbol),
            "message": "unknown strategy",
        }

    trade = {
        "symbol": payload.symbol.upper(),
        "side": payload.side,
        "qty": float(payload.qty),
        "entry_price": float(payload.entry_price),
        "leverage": float(payload.leverage),
    }

    current_positions = payload.current_positions or []
    result = risk_engine.evaluate_trade(
        trade=trade,
        current_positions=current_positions,
        current_daily_pnl=float(payload.current_daily_pnl),
    )

    market_provenance = _market_provenance(payload.symbol)
    usage = _usage_summary(current_positions, float(payload.current_daily_pnl))

    if result["allowed"]:
        verdict = "ALLOW_CAPPED" if usage["position_usage_pct"] >= 75.0 or usage["daily_loss_usage_pct"] >= 75.0 else "ALLOW"
        action_plan = _action_plan_from_usage(usage["position_usage_pct"], usage["daily_loss_usage_pct"])
        status = "ok"
        message = "intent allowed by risk firewall"
        if verdict == "ALLOW_CAPPED":
            message = "intent allowed by risk firewall but should be trimmed to preserve buffer"
    else:
        verdict = "REJECT"
        action_plan = "REJECT"
        status = "rejected"
        message = "intent rejected by risk firewall"

    return {
        "status": status,
        "verdict": verdict,
        "action_plan": action_plan,
        "strategy_id": strategy_id,
        "active_strategy": get_active_strategy_id(),
        "trade": trade,
        "risk_check": result,
        "risk_usage": usage,
        "market_provenance": market_provenance,
        "message": message,
    }


@app.get("/risk-view")
def risk_view(symbol: str = "AAPLUSDT") -> dict[str, Any]:
    live_positions = positions().get("positions", [])
    pnl_snapshot = pnl()
    usage = _usage_summary(live_positions, float(pnl_snapshot.get("daily_pnl", 0.0) or 0.0))
    action_plan = _action_plan_from_usage(usage["position_usage_pct"], usage["daily_loss_usage_pct"])
    return {
        "symbol": symbol.upper(),
        "action_plan": action_plan,
        "risk_usage": usage,
        "market_provenance": _market_provenance(symbol),
        "positions": live_positions,
        "pnl": pnl_snapshot,
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
def paper_trade(payload: TradeRequest, user: AuthenticatedUser = Depends(current_user)) -> dict[str, Any]:
    user_execution_client = execution_client_for(user)
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

    execution = user_execution_client.place_market_order(order)
    return {"order": order, "risk": result["risk"], **execution}


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Priva backend is live."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
