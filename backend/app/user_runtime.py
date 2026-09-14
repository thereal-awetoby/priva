from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any

from app import agent_loop
from app.market_data import BitgetMarketDataService
from app.paper_execution import BitgetPaperExecutionClient
from app.risk_engine import RiskEngine
from app.supabase_logging import SupabaseCycleLogger
from app.strategy import get_active_strategy_id


@dataclass
class UserRuntime:
    user_id: str
    execution_client: BitgetPaperExecutionClient
    risk_engine: RiskEngine
    cycle_logger: SupabaseCycleLogger
    symbols: list[str]
    strategy_id: str
    strategy_by_symbol: dict[str, str]
    market_type: str
    take_profit_pct: float
    stop_loss_pct: float
    close_on_signal_violation: bool
    task: asyncio.Task | None = None
    stop_event: asyncio.Event | None = None


class UserRuntimeRegistry:
    def __init__(self) -> None:
        self._runtimes: dict[str, UserRuntime] = {}

    def get(self, user_id: str) -> UserRuntime | None:
        return self._runtimes.get(user_id)

    def start(self, user_id: str, execution_client: BitgetPaperExecutionClient) -> UserRuntime:
        current = self._runtimes.get(user_id)
        if current and current.task and not current.task.done():
            return current

        symbols = [
            symbol.strip().upper()
            for symbol in os.getenv("AGENT_WATCHED_SYMBOLS", "AAPLUSDT,TSLAUSDT").split(",")
            if symbol.strip()
        ]
        cycle_logger = SupabaseCycleLogger(user_id=user_id)
        settings = cycle_logger.fetch_user_settings(user_id)
        configured_symbols = settings.get("symbols")
        if isinstance(configured_symbols, list) and configured_symbols:
            symbols = [str(symbol).upper() for symbol in configured_symbols]
        risk_engine = RiskEngine(
            max_position_size=float(settings.get("max_position_size", 25000)),
            max_daily_loss=float(settings.get("max_daily_loss", 1500)),
            max_leverage=float(settings.get("max_leverage", 5)),
            enabled=bool(settings.get("risk_enabled", True)),
            allowed_symbols=settings.get("allowed_symbols") or None,
        )
        runtime = UserRuntime(
            user_id=user_id,
            execution_client=execution_client,
            risk_engine=risk_engine,
            cycle_logger=cycle_logger,
            symbols=symbols,
            strategy_id=str(settings.get("strategy_id") or get_active_strategy_id()),
            strategy_by_symbol=settings.get("strategy_by_symbol") if isinstance(settings.get("strategy_by_symbol"), dict) else {},
            market_type=str(settings.get("market", "futures")),
            take_profit_pct=float(settings.get("take_profit_pct", 5)),
            stop_loss_pct=float(settings.get("stop_loss_pct", 2)),
            close_on_signal_violation=bool(settings.get("close_on_signal_violation", True)),
            stop_event=asyncio.Event(),
        )
        runtime.task = asyncio.create_task(self._run(runtime))
        self._runtimes[user_id] = runtime
        return runtime

    async def _run(self, runtime: UserRuntime) -> None:
        interval = int(os.getenv("AGENT_LOOP_INTERVAL_SECONDS", "300"))
        market_service = BitgetMarketDataService()
        while runtime.stop_event and not runtime.stop_event.is_set():
            for symbol in runtime.symbols:
                if runtime.stop_event.is_set():
                    break
                await agent_loop.run_cycle(
                    symbol,
                    market_service=market_service,
                    risk_engine=runtime.risk_engine,
                    execution_client=runtime.execution_client,
                    cycle_logger=runtime.cycle_logger,
                    strategy_id=runtime.strategy_id,
                    strategy_by_symbol=runtime.strategy_by_symbol,
                    market_type=runtime.market_type,
                    take_profit_pct=runtime.take_profit_pct,
                    stop_loss_pct=runtime.stop_loss_pct,
                    close_on_signal_violation=runtime.close_on_signal_violation,
                )
            try:
                await asyncio.wait_for(runtime.stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    async def stop(self, user_id: str) -> bool:
        runtime = self._runtimes.pop(user_id, None)
        if not runtime:
            return False
        if runtime.stop_event:
            runtime.stop_event.set()
        if runtime.task and not runtime.task.done():
            runtime.task.cancel()
            await asyncio.gather(runtime.task, return_exceptions=True)
        return True

    def status(self, user_id: str) -> dict[str, Any]:
        runtime = self._runtimes.get(user_id)
        return {
            "running": bool(runtime and runtime.task and not runtime.task.done()),
            "user_id": user_id,
            "symbols": runtime.symbols if runtime else [],
            "strategy_id": runtime.strategy_id if runtime else None,
            "strategy_by_symbol": runtime.strategy_by_symbol if runtime else {},
            "market": runtime.market_type if runtime else None,
            "take_profit_pct": runtime.take_profit_pct if runtime else None,
            "stop_loss_pct": runtime.stop_loss_pct if runtime else None,
        }


user_runtime_registry = UserRuntimeRegistry()