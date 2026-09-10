from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from app.market_data import BitgetMarketDataService
from app.risk_engine import RiskEngine

app = FastAPI(
    title="Priva Backend",
    description="Builder B backend scaffolding for Priva trading agent",
    version="0.1.0",
)

market_service = BitgetMarketDataService()
risk_engine = RiskEngine()


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
        "qty": 5,
        "entry_price": float(ticker.get("last_price", 0.0) or 0.0),
        "leverage": 1.0,
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
    asyncio.create_task(periodic_market_loop())


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


@app.get("/pnl")
def pnl() -> dict[str, Any]:
    return {
        "unrealized_pnl": 742.38,
        "realized_pnl": 124.9,
        "daily_pnl": 216.58,
        "total_pnl": 867.28,
        "currency": "USD",
    }


@app.get("/risk-usage")
def risk_usage() -> dict[str, Any]:
    return {
        "max_position_size": 25000,
        "current_position_size": 4124.88,
        "max_daily_loss": 1500,
        "current_daily_loss": 380.4,
        "max_leverage": 5.0,
        "current_leverage": 2.8,
        "usage_percent": {
            "position_size": 16.5,
            "daily_loss": 25.4,
            "leverage": 56.0,
        },
    }


@app.get("/activity-log")
def activity_log() -> dict[str, Any]:
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
                "id": "playbook_momentum",
                "name": "Momentum Breakout",
                "type": "playbook",
                "status": "inactive",
                "description": "Long when trend and volume accelerate above baseline.",
            },
            {
                "id": "custom_rsi",
                "name": "RSI Mean Reversion",
                "type": "custom",
                "status": "active",
                "description": "Buy oversold conditions and close when momentum fades.",
            },
        ]
    }


@app.post("/strategies/{strategy_id}/activate")
def activate_strategy(strategy_id: str) -> dict[str, Any]:
    return {
        "strategy_id": strategy_id,
        "status": "activated",
        "mode": "strategy",
        "active": True,
    }


@app.get("/kill-switch")
def get_kill_switch() -> dict[str, Any]:
    return {"enabled": False, "message": "Agent loop is active."}


@app.post("/kill-switch")
def set_kill_switch(payload: KillSwitchRequest) -> dict[str, Any]:
    return {
        "enabled": payload.enabled,
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
    result = risk_engine.evaluate_trade(
        trade=payload.model_dump(),
        current_positions=[],
        current_daily_pnl=0.0,
    )

    if not result["allowed"]:
        return {
            "status": "rejected",
            "order": payload.model_dump(),
            "reasons": result["reasons"],
            "risk": result["risk"],
        }

    return {
        "status": "accepted",
        "order": payload.model_dump(),
        "order_id": f"paper_{payload.symbol.lower()}_{int(payload.entry_price * 100)}",
        "message": "Paper trade created and passed risk checks.",
        "risk": result["risk"],
    }


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Priva backend is live."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
