from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any

from app import agent_loop
from app.market_data import BitgetMarketDataService
from app.paper_execution import BitgetPaperExecutionClient
from app.risk_engine import RiskEngine
from app.supabase_logging import SupabaseCycleLogger
from app.strategy import configure_builtin_strategy, get_active_strategy_id, register_custom_strategy

logger = logging.getLogger("priva.user_runtime")


@dataclass
class WorkerRuntime:
    profile: str
    mode: str
    market: str
    strategy_id: str | None
    risk_engine: RiskEngine
    task: asyncio.Task | None = None
    last_error: str | None = None
    last_cycle_status: str | None = None
    last_persistence_status: str | None = None


@dataclass
class UserRuntime:
    user_id: str
    execution_client: BitgetPaperExecutionClient
    cycle_logger: SupabaseCycleLogger
    symbols: list[str]
    strategy_id: str
    strategy_by_symbol: dict[str, str]
    take_profit_pct: float
    stop_loss_pct: float
    close_on_signal_violation: bool
    stop_event: asyncio.Event | None = None
    risk_settings: dict[str, Any] | None = None
    profiles: list[str] | None = None
    workers: dict[str, WorkerRuntime] | None = None

    @staticmethod
    def normalize_profiles(profiles: Any, *, fallback_market: str, strategy_id: str | None) -> list[str]:
        candidates = profiles if isinstance(profiles, list) else []
        normalized = []
        for candidate in candidates:
            value = str(candidate).strip().lower()
            if value.count(":") != 1:
                continue
            mode, market = value.split(":")
            if mode in {"autonomous", "strategy"} and market in {"spot", "futures"}:
                normalized.append(f"{mode}:{market}")
        if normalized:
            return list(dict.fromkeys(normalized))
        mode = "strategy" if strategy_id else "autonomous"
        market = fallback_market if fallback_market in {"spot", "futures"} else "futures"
        return [f"{mode}:{market}"]

    def _new_risk_engine(self) -> RiskEngine:
        return RiskEngine(**(self.risk_settings or {}))

    def apply_profiles(self, profiles: list[str]) -> None:
        normalized = self.normalize_profiles(profiles, fallback_market="futures", strategy_id=self.strategy_id)
        if self.workers:
            for worker in self.workers.values():
                if worker.task and not worker.task.done():
                    worker.task.cancel()
        self.profiles = normalized
        self.workers = {}
        for profile in normalized:
            mode, market = profile.split(":")
            worker = WorkerRuntime(
                profile=profile,
                mode=mode,
                market=market,
                strategy_id=self.strategy_id if mode == "strategy" else None,
                risk_engine=self._new_risk_engine(),
            )
            worker.task = asyncio.create_task(self._run_worker(worker))
            self.workers[profile] = worker

    async def _run_worker(self, worker: WorkerRuntime) -> None:
        interval = int(os.getenv("AGENT_LOOP_INTERVAL_SECONDS", "300"))
        market_service = BitgetMarketDataService()
        while self.stop_event and not self.stop_event.is_set():
            try:
                result = None
                if worker.strategy_id == "pairs_trading" and len(self.symbols) >= 2:
                    result = await agent_loop.run_pair_cycle(
                        self.symbols[0], self.symbols[1],
                        market_service=market_service,
                        risk_engine=worker.risk_engine,
                        execution_client=self.execution_client,
                        cycle_logger=self.cycle_logger,
                        market_type=worker.market,
                        stop_loss_pct=self.stop_loss_pct,
                    )
                else:
                    for symbol in self.symbols:
                        if self.stop_event.is_set():
                            break
                        result = await agent_loop.run_cycle(
                            symbol,
                            market_service=market_service,
                            risk_engine=worker.risk_engine,
                            execution_client=self.execution_client,
                            cycle_logger=self.cycle_logger,
                            strategy_id=worker.strategy_id,
                            strategy_by_symbol=self.strategy_by_symbol,
                            market_type=worker.market,
                            take_profit_pct=self.take_profit_pct,
                            stop_loss_pct=self.stop_loss_pct,
                            close_on_signal_violation=self.close_on_signal_violation,
                            mode=worker.mode,
                        )
                worker.last_error = None
                if isinstance(result, dict):
                    worker.last_cycle_status = str(result.get("status"))
                    persistence = result.get("persistence")
                    if isinstance(persistence, dict):
                        worker.last_persistence_status = str(persistence.get("status"))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                worker.last_error = str(exc)
                logger.exception("User runtime worker failed for %s (%s)", self.user_id, worker.profile)
            try:
                await asyncio.wait_for(self.stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass


class UserRuntimeRegistry:
    def __init__(self) -> None:
        self._runtimes: dict[str, UserRuntime] = {}

    def get(self, user_id: str) -> UserRuntime | None:
        return self._runtimes.get(user_id)

    def start(self, user_id: str, execution_client: BitgetPaperExecutionClient) -> UserRuntime:
        current = self._runtimes.get(user_id)
        if current and any(worker.task and not worker.task.done() for worker in (current.workers or {}).values()):
            return current

        symbols = [
            symbol.strip().upper()
            for symbol in os.getenv("AGENT_WATCHED_SYMBOLS", "AAPLUSDT,TSLAUSDT").split(",")
            if symbol.strip()
        ]
        cycle_logger = SupabaseCycleLogger(user_id=user_id)
        for record in cycle_logger.fetch_custom_strategies(user_id):
            definition = record.get("definition")
            strategy_id = record.get("strategy_id")
            if strategy_id and isinstance(definition, dict):
                register_custom_strategy(
                    str(strategy_id),
                    definition,
                    name=str(record.get("name") or "").strip() or None,
                    description=str(record.get("description") or "").strip() or None,
                )
        settings = cycle_logger.fetch_user_settings(user_id)
        strategy_id = str(settings.get("strategy_id") or get_active_strategy_id())
        strategy_config = settings.get("strategy_config")
        if isinstance(strategy_config, dict):
            try:
                configure_builtin_strategy(strategy_id, strategy_config)
            except ValueError:
                strategy_config = None
        configured_symbols = settings.get("symbols")
        if isinstance(configured_symbols, list) and configured_symbols:
            symbols = [str(symbol).upper() for symbol in configured_symbols]
        risk_settings = {
            "max_position_size": float(settings.get("max_position_size", 25000)),
            "max_daily_loss": float(settings.get("max_daily_loss", 1500)),
            "max_leverage": float(settings.get("max_leverage", 5)),
            "enabled": bool(settings.get("risk_enabled", True)),
            "allowed_symbols": settings.get("allowed_symbols") or None,
        }
        runtime = UserRuntime(
            user_id=user_id,
            execution_client=execution_client,
            cycle_logger=cycle_logger,
            symbols=symbols,
            strategy_id=strategy_id,
            strategy_by_symbol=settings.get("strategy_by_symbol") if isinstance(settings.get("strategy_by_symbol"), dict) else {},
            take_profit_pct=float(settings.get("take_profit_pct", 5)),
            stop_loss_pct=float(settings.get("stop_loss_pct", 2)),
            close_on_signal_violation=bool(settings.get("close_on_signal_violation", True)),
            stop_event=asyncio.Event(),
            risk_settings=risk_settings,
            profiles=self.normalize_profiles(
                settings.get("execution_profiles"),
                fallback_market=str(settings.get("market", "futures")),
                strategy_id=strategy_id if settings.get("strategy_id") else None,
            ),
            workers={},
        )
        runtime.apply_profiles(runtime.profiles or [])
        self._runtimes[user_id] = runtime
        return runtime

    async def stop(self, user_id: str) -> bool:
        runtime = self._runtimes.pop(user_id, None)
        if not runtime:
            return False
        if runtime.stop_event:
            runtime.stop_event.set()
        tasks = [worker.task for worker in (runtime.workers or {}).values() if worker.task and not worker.task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        return True

    def status(self, user_id: str) -> dict[str, Any]:
        runtime = self._runtimes.get(user_id)
        workers = runtime.workers or {} if runtime else {}
        return {
            "running": any(worker.task and not worker.task.done() for worker in workers.values()),
            "user_id": user_id,
            "symbols": runtime.symbols if runtime else [],
            "last_error": next((worker.last_error for worker in workers.values() if worker.last_error), None),
            "last_cycle_status": next((worker.last_cycle_status for worker in workers.values() if worker.last_cycle_status), None),
            "last_persistence_status": next((worker.last_persistence_status for worker in workers.values() if worker.last_persistence_status), None),
            "supabase_logging_configured": bool(runtime and runtime.cycle_logger.configured),
            "strategy_id": runtime.strategy_id if runtime else None,
            "strategy_by_symbol": runtime.strategy_by_symbol if runtime else {},
            "market": (runtime.profiles[0].split(":", 1)[1] if runtime and runtime.profiles else None),
            "execution_profiles": runtime.profiles if runtime else [],
            "workers": {
                profile: {
                    "mode": worker.mode,
                    "market": worker.market,
                    "running": bool(worker.task and not worker.task.done()),
                    "last_error": worker.last_error,
                    "last_cycle_status": worker.last_cycle_status,
                }
                for profile, worker in workers.items()
            },
            "take_profit_pct": runtime.take_profit_pct if runtime else None,
            "stop_loss_pct": runtime.stop_loss_pct if runtime else None,
        }


user_runtime_registry = UserRuntimeRegistry()