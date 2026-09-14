from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from math import sqrt
from typing import Any, Literal

import requests


@dataclass(frozen=True)
class Decision:
    action: Literal["buy", "sell", "hold"]
    size: float
    leverage: float
    reason: str
    signal_strength: float = 0.0
    take_profit_pct: float | None = None
    stop_loss_pct: float | None = None


def _adaptive_leverage(signal_strength: float) -> float:
    """Scale default futures leverage with signal confidence, capped at 3x."""
    strength = min(1.0, max(0.0, float(signal_strength)))
    if strength >= 0.66:
        return 3.0
    if strength >= 0.33:
        return 2.0
    return 1.0


def _momentum_strategy(ticker: dict[str, Any]) -> Decision:
    if ticker.get("status") != "live":
        return Decision("hold", 0.0, 1.0, "market feed unavailable; fallback mode active")

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

    rounded_strength = round(strength, 4)
    leverage = _adaptive_leverage(rounded_strength) if signal != "hold" else 1.0
    return Decision(signal, 1.0 if signal != "hold" else 0.0, leverage, "simple price-vs-open momentum signal", rounded_strength)


def _mean_reversion_strategy(ticker: dict[str, Any]) -> Decision:
    if ticker.get("status") != "live":
        return Decision("hold", 0.0, 1.0, "market feed unavailable; fallback mode active")

    last_price = float(ticker.get("last_price", 0.0) or 0.0)
    open_price = float(ticker.get("open_price", 0.0) or 0.0)
    if last_price <= 0 or open_price <= 0:
        return Decision("hold", 0.0, 1.0, "invalid market prices")

    config = _get_builtin_strategy_config("mean_reversion")
    threshold_pct = float(config.get("threshold_pct", 1.0) or 1.0)
    threshold = threshold_pct / 100.0

    deviation = (last_price - open_price) / open_price
    if deviation >= threshold:
        strength = round(min(1.0, deviation / max(threshold, 0.01)), 4)
        leverage_signal = min(1.0, deviation / max(threshold * 4, 0.01))
        return Decision("sell", 1.0, _adaptive_leverage(leverage_signal), f"mean reversion: price extended above open by {threshold_pct}%", strength)
    if deviation <= -threshold:
        strength = round(min(1.0, abs(deviation) / max(threshold, 0.01)), 4)
        leverage_signal = min(1.0, abs(deviation) / max(threshold * 4, 0.01))
        return Decision("buy", 1.0, _adaptive_leverage(leverage_signal), f"mean reversion: price extended below open by {threshold_pct}%", strength)
    return Decision("hold", 0.0, 1.0, "mean reversion: price within neutral band", 0.0)


STRATEGY_CATALOG = {
    "momentum_breakout": {
        "id": "momentum_breakout",
        "name": "Momentum Breakout",
        "type": "prebuilt",
        "description": "Long when trend and volume accelerate above baseline.",
    },
    "mean_reversion": {
        "id": "mean_reversion",
        "name": "Mean Reversion",
        "type": "prebuilt",
        "description": "Fade moves that extend at least 1% away from the opening price.",
    },
}

STRATEGIES = {
    "momentum_breakout": _momentum_strategy,
    "mean_reversion": _mean_reversion_strategy,
}

_registered_strategy_catalog = dict(STRATEGY_CATALOG)
_active_strategy_id = "momentum_breakout"
_builtin_strategy_configs: dict[str, dict[str, Any]] = {}
_symbol_strategy_ids: dict[str, str] = {}


def _set_builtin_strategy_config(strategy_id: str, config: dict[str, Any]) -> None:
    if strategy_id not in STRATEGIES:
        raise ValueError(f"unknown strategy: {strategy_id}")

    normalized = dict(config or {})
    existing = dict(_builtin_strategy_configs.get(strategy_id, {}) or {})
    existing.update(normalized)
    _builtin_strategy_configs[strategy_id] = existing


def _get_builtin_strategy_config(strategy_id: str) -> dict[str, Any]:
    return dict(_builtin_strategy_configs.get(strategy_id, {}) or {})


def _apply_builtin_strategy_config(strategy_id: str, decision: Decision) -> Decision:
    config = _get_builtin_strategy_config(strategy_id)
    if not config:
        return decision

    size = float(config.get("position_size", decision.size) or decision.size)
    leverage = float(config.get("leverage", decision.leverage) or decision.leverage)
    take_profit_pct = config.get("take_profit_pct", decision.take_profit_pct)
    stop_loss_pct = config.get("stop_loss_pct", decision.stop_loss_pct)

    return Decision(
        action=decision.action,
        size=size,
        leverage=leverage,
        reason=decision.reason,
        signal_strength=decision.signal_strength,
        take_profit_pct=take_profit_pct,
        stop_loss_pct=stop_loss_pct,
    )


def configure_builtin_strategy(strategy_id: str, config: dict[str, Any]) -> None:
    if strategy_id not in STRATEGIES:
        raise ValueError(f"unknown strategy: {strategy_id}")

    if not isinstance(config, dict):
        raise ValueError("strategy configuration must be an object")

    normalized = {}

    if "threshold_pct" in config:
        try:
            normalized["threshold_pct"] = float(config["threshold_pct"])
        except (TypeError, ValueError) as exc:
            raise ValueError("strategy threshold_pct must be numeric") from exc

    for field in ("position_size", "size"):
        if field in config:
            try:
                normalized["position_size"] = float(config[field])
            except (TypeError, ValueError) as exc:
                raise ValueError("strategy position_size must be numeric") from exc
            if normalized["position_size"] <= 0:
                raise ValueError("strategy position_size must be greater than zero")

    for field in ("leverage",):
        if field in config:
            try:
                normalized[field] = float(config[field])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"strategy {field} must be numeric") from exc
            if normalized[field] <= 0:
                raise ValueError(f"strategy {field} must be greater than zero")

    for field in ("take_profit_pct", "take_profit", "stop_loss_pct", "stop_loss"):
        if field in config and config[field] is not None:
            try:
                normalized[field.replace("take_profit", "take_profit_pct").replace("stop_loss", "stop_loss_pct")] = float(config[field])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"strategy {field} must be numeric") from exc

    _set_builtin_strategy_config(strategy_id, normalized)


def _coerce_price(value: Any) -> float:
    return float(value or 0.0)


def _price_from_candle(candle: dict[str, Any]) -> float:
    if not candle:
        return 0.0
    return _coerce_price(candle.get("close", candle.get("last_price", candle.get("last", 0.0))))


def _build_ticker_from_candle(candle: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "live",
        "last_price": _price_from_candle(candle),
        "open_price": _coerce_price(candle.get("open", candle.get("open_price", 0.0))),
    }


def _position_pnl(position: dict[str, Any], price: float) -> float:
    if not position:
        return 0.0
    if position["side"] == "buy":
        return position["qty"] * (price - position["entry_price"])
    return position["qty"] * (position["entry_price"] - price)


def _safe_mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _safe_std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = _safe_mean(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return sqrt(variance)


def backtest_strategy(strategy_id: str, candles: list[dict[str, Any]], initial_capital: float = 10000.0) -> dict[str, Any]:
    if strategy_id not in STRATEGIES:
        raise ValueError(f"unknown strategy: {strategy_id}")
    if not candles:
        raise ValueError("candles are required")

    initial_capital = max(float(initial_capital or 0.0), 0.0)
    if initial_capital <= 0:
        raise ValueError("initial_capital must be greater than zero")

    realized_pnl = 0.0
    position: dict[str, Any] | None = None
    closed_trades: list[dict[str, Any]] = []
    equity_curve = [initial_capital]

    for candle in candles:
        price = _price_from_candle(candle)
        ticker = _build_ticker_from_candle(candle)
        decision = STRATEGIES[strategy_id](ticker)
        target_side = decision.action if decision.action in {"buy", "sell"} else None

        if target_side is None:
            current_equity = initial_capital + realized_pnl + (_position_pnl(position, price) if position else 0.0)
            equity_curve.append(current_equity)
            continue

        if position is None:
            position = {
                "side": target_side,
                "entry_price": price,
                "qty": initial_capital / max(price, 1.0),
            }
            current_equity = initial_capital + realized_pnl + _position_pnl(position, price)
            equity_curve.append(current_equity)
            continue

        if position["side"] != target_side:
            close_pnl = _position_pnl(position, price)
            realized_pnl += close_pnl
            closed_trades.append(
                {
                    "side": position["side"],
                    "entry_price": position["entry_price"],
                    "exit_price": price,
                    "pnl": close_pnl,
                }
            )
            position = {
                "side": target_side,
                "entry_price": price,
                "qty": initial_capital / max(price, 1.0),
            }

        current_equity = initial_capital + realized_pnl + (_position_pnl(position, price) if position else 0.0)
        equity_curve.append(current_equity)

    if position is not None:
        close_pnl = _position_pnl(position, _price_from_candle(candles[-1]))
        realized_pnl += close_pnl
        closed_trades.append(
            {
                "side": position["side"],
                "entry_price": position["entry_price"],
                "exit_price": _price_from_candle(candles[-1]),
                "pnl": close_pnl,
            }
        )
        equity_curve.append(initial_capital + realized_pnl)
        position = None

    period_returns = []
    for previous, current in zip(equity_curve, equity_curve[1:]):
        if previous == 0:
            continue
        period_returns.append((current / previous) - 1)

    total_return = (equity_curve[-1] - initial_capital) / initial_capital if initial_capital else 0.0
    if closed_trades:
        winning_trades = sum(1 for trade in closed_trades if trade["pnl"] > 0)
        win_rate = winning_trades / len(closed_trades)
    else:
        win_rate = 0.0

    peak_value = initial_capital
    max_drawdown = 0.0
    for value in equity_curve:
        if value > peak_value:
            peak_value = value
        if peak_value == 0:
            continue
        drawdown = (peak_value - value) / peak_value
        if drawdown > max_drawdown:
            max_drawdown = drawdown

    sharpe_ratio = 0.0
    if period_returns:
        mean_return = _safe_mean(period_returns)
        std_return = _safe_std(period_returns)
        if std_return > 0:
            sharpe_ratio = (mean_return / std_return) * sqrt(len(period_returns))

    return {
        "strategy_id": strategy_id,
        "status": "completed",
        "candles_analyzed": len(candles),
        "metrics": {
            "return": round(total_return, 4),
            "win_rate": round(win_rate, 4),
            "sharpe_ratio": round(sharpe_ratio, 4),
            "max_drawdown": round(max_drawdown, 4),
        },
        "trade_count": len(closed_trades),
    }


def _extract_json_from_content(content: str) -> dict[str, Any]:
    stripped = (content or "").strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped, flags=re.IGNORECASE)

    json_match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    if json_match:
        stripped = json_match.group(0)

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError("provider response was not valid JSON") from exc

    if not isinstance(parsed, dict):
        raise ValueError("provider response did not contain a JSON object")

    return parsed


def _parse_with_gemini(text: str) -> dict[str, Any]:
    api_key = (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("GROK_API_KEY")
        or os.getenv("XAI_API_KEY")
        or os.getenv("QWEN_API_KEY")
        or os.getenv("DASHSCOPE_API_KEY")
    )
    if not api_key:
        raise ValueError("Gemini API key is required. Set GEMINI_API_KEY or GOOGLE_API_KEY.")

    base_url = (os.getenv("GEMINI_API_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    model = os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"

    response = requests.post(
        f"{base_url}/models/{model}:generateContent?key={api_key}",
        headers={
            "Content-Type": "application/json",
        },
        json={
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "You convert a natural-language trading strategy into JSON. Return a JSON object only. "
                                "Supported object shapes: {\"kind\":\"builtin\",\"target_strategy\":\"mean_reversion\",\"threshold_pct\":1.0} "
                                "or {\"kind\":\"builtin\",\"target_strategy\":\"momentum_breakout\",\"threshold_pct\":1.0}.\n\n"
                                f"{text}"
                            )
                        }
                    ]
                }
            ],
            "generationConfig": {"temperature": 0},
        },
        timeout=30,
    )

    if response.status_code >= 400:
        raise ValueError(
            f"Gemini parsing request failed with status {response.status_code}: {response.text}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise ValueError("Gemini response was not valid JSON") from exc

    candidates = payload.get("candidates") or []
    if not candidates or not isinstance(candidates, list):
        raise ValueError("Gemini response did not include any candidates")

    candidate = candidates[0]
    content = candidate.get("content", {})
    parts = content.get("parts") or []
    if not parts or not isinstance(parts, list):
        raise ValueError("Gemini response did not include any content parts")

    text_blocks = []
    for part in parts:
        if isinstance(part, dict) and part.get("text"):
            text_blocks.append(part.get("text", ""))

    if not text_blocks:
        raise ValueError("Gemini response did not include text content")

    parsed = _extract_json_from_content("".join(text_blocks))

    if parsed.get("kind") == "builtin":
        if parsed.get("target_strategy") not in {"mean_reversion", "momentum_breakout"}:
            raise ValueError("Gemini returned an unsupported builtin strategy")
        if parsed.get("threshold_pct") is None:
            raise ValueError("Gemini response is missing threshold_pct")
        return parsed

    raise ValueError("Gemini returned an unsupported strategy shape")


def parse_natural_language_strategy(
    text: str,
    *,
    use_gemini: bool = False,
    use_grok: bool = False,
    use_qwen: bool | None = None,
) -> dict[str, Any]:
    normalized = (text or "").strip()
    if not normalized:
        raise ValueError("strategy text is required")

    if use_qwen is not None:
        use_gemini = use_gemini or use_qwen

    if use_gemini or use_grok:
        return _parse_with_gemini(normalized)

    lowered = normalized.lower()
    threshold_match = re.search(r"(\d+(?:\.\d+)?)\s*%", lowered)
    if not threshold_match:
        raise ValueError("natural-language strategy requires an explicit percentage threshold")

    threshold_pct = float(threshold_match.group(1))

    if "mean reversion" in lowered or "fade moves" in lowered or "fades moves" in lowered:
        return {
            "kind": "builtin",
            "target_strategy": "mean_reversion",
            "threshold_pct": threshold_pct,
            "raw_text": normalized,
        }

    if "momentum" in lowered or "breakout" in lowered:
        return {
            "kind": "builtin",
            "target_strategy": "momentum_breakout",
            "threshold_pct": threshold_pct,
            "raw_text": normalized,
        }

    raise ValueError("unsupported natural-language strategy")


def parse_structured_strategy(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("strategy payload must be an object")

    if payload.get("target_strategy"):
        target_strategy = str(payload.get("target_strategy")).lower()
        if target_strategy not in STRATEGIES:
            raise ValueError("structured strategy target_strategy must be a supported builtin strategy")

        threshold_pct = payload.get("threshold_pct", payload.get("threshold"))
        if threshold_pct is not None:
            try:
                threshold_pct = float(threshold_pct)
            except (TypeError, ValueError) as exc:
                raise ValueError("structured strategy threshold_pct must be numeric") from exc
        else:
            threshold_pct = 1.0 if target_strategy == "mean_reversion" else None

        position_size_raw = payload.get("position_size", payload.get("size", 1.0))
        if position_size_raw is None:
            position_size_raw = 1.0
        try:
            position_size = float(position_size_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("structured strategy position_size must be numeric") from exc
        if position_size <= 0:
            raise ValueError("structured strategy position_size must be greater than zero")

        leverage_raw = payload.get("leverage", 1.0)
        try:
            leverage = float(leverage_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("structured strategy leverage must be numeric") from exc
        if leverage <= 0:
            raise ValueError("structured strategy leverage must be greater than zero")

        take_profit_pct = payload.get("take_profit_pct", payload.get("take_profit"))
        stop_loss_pct = payload.get("stop_loss_pct", payload.get("stop_loss"))

        result = {
            "kind": "builtin",
            "target_strategy": target_strategy,
            "position_size": position_size,
            "leverage": leverage,
        }
        if threshold_pct is not None:
            result["threshold_pct"] = threshold_pct
        if take_profit_pct is not None:
            result["take_profit_pct"] = float(take_profit_pct)
        if stop_loss_pct is not None:
            result["stop_loss_pct"] = float(stop_loss_pct)
        return result

    action = str(payload.get("action", "buy")).lower()
    if action not in {"buy", "sell"}:
        raise ValueError("structured strategy action must be buy or sell")

    comparison = str(payload.get("comparison", "open")).lower()
    if comparison not in {"open", "close"}:
        raise ValueError("structured strategy comparison must be open or close")

    threshold_pct = payload.get("threshold_pct", payload.get("threshold"))
    if threshold_pct is None:
        raise ValueError("structured strategy requires a threshold_pct value")
    try:
        threshold_pct = float(threshold_pct)
    except (TypeError, ValueError) as exc:
        raise ValueError("structured strategy threshold_pct must be numeric") from exc

    position_size_raw = payload.get("position_size", payload.get("size", 1.0))
    if position_size_raw is None:
        position_size_raw = 1.0

    try:
        position_size = float(position_size_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("structured strategy position_size must be numeric") from exc

    if position_size <= 0:
        raise ValueError("structured strategy position_size must be greater than zero")

    leverage_raw = payload.get("leverage", 1.0)
    try:
        leverage = float(leverage_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("structured strategy leverage must be numeric") from exc
    if leverage <= 0:
        raise ValueError("structured strategy leverage must be greater than zero")

    take_profit_pct = payload.get("take_profit_pct", payload.get("take_profit"))
    stop_loss_pct = payload.get("stop_loss_pct", payload.get("stop_loss"))

    result = {
        "kind": "custom",
        "action": action,
        "comparison": comparison,
        "threshold_pct": threshold_pct,
        "position_size": position_size,
        "leverage": leverage,
    }
    if take_profit_pct is not None:
        result["take_profit_pct"] = float(take_profit_pct)
    if stop_loss_pct is not None:
        result["stop_loss_pct"] = float(stop_loss_pct)
    return result


def decision_to_dict(decision: Decision) -> dict[str, Any]:
    return {**asdict(decision), "status": "logged"}


def get_active_strategy_id() -> str:
    return _active_strategy_id


def activate_strategy(strategy_id: str) -> bool:
    global _active_strategy_id
    if strategy_id not in STRATEGIES:
        return False
    _active_strategy_id = strategy_id
    return True


def configure_symbol_strategies(strategy_by_symbol: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for symbol, strategy_id in strategy_by_symbol.items():
        normalized_symbol = str(symbol).strip().upper()
        if strategy_id not in STRATEGIES:
            raise ValueError(f"unknown strategy: {strategy_id}")
        if normalized_symbol:
            normalized[normalized_symbol] = strategy_id
    _symbol_strategy_ids.clear()
    _symbol_strategy_ids.update(normalized)
    return dict(_symbol_strategy_ids)


def get_strategy_for_symbol(symbol: str) -> str:
    return _symbol_strategy_ids.get(str(symbol).strip().upper(), _active_strategy_id)


def register_custom_strategy(strategy_id: str, parsed_strategy: dict[str, Any]) -> None:
    strategy_type = str(parsed_strategy.get("kind", "custom")).lower()
    if strategy_type != "custom":
        return

    action = str(parsed_strategy.get("action", "buy")).lower()
    comparison = str(parsed_strategy.get("comparison", "open")).lower()
    threshold_pct = float(parsed_strategy.get("threshold_pct", 0.0) or 0.0)
    position_size = float(parsed_strategy.get("position_size", parsed_strategy.get("size", 1.0)) or 1.0)
    leverage = float(parsed_strategy.get("leverage", 1.0) or 1.0)
    take_profit_pct = parsed_strategy.get("take_profit_pct")
    stop_loss_pct = parsed_strategy.get("stop_loss_pct")

    def custom_strategy(ticker: dict[str, Any]) -> Decision:
        if ticker.get("status") != "live":
            return Decision("hold", 0.0, 1.0, "market feed unavailable; fallback mode active")

        last_price = float(ticker.get("last_price", 0.0) or 0.0)
        open_price = float(ticker.get("open_price", 0.0) or 0.0)
        comparison_price = float(ticker.get("close_price", open_price) or open_price)
        if comparison == "close":
            comparison_price = float(ticker.get("close_price", 0.0) or 0.0)
        if comparison_price <= 0 or last_price <= 0:
            return Decision("hold", 0.0, 1.0, "invalid market prices")

        deviation = (last_price - comparison_price) / comparison_price
        threshold = threshold_pct / 100.0

        if action == "buy":
            if deviation >= threshold:
                strength = min(1.0, max(0.0, deviation / max(threshold, 0.01)))
                return Decision(
                    "buy",
                    position_size,
                    leverage,
                    f"custom strategy: price above {comparison} by {threshold_pct}%",
                    round(strength, 4),
                    take_profit_pct,
                    stop_loss_pct,
                )
            return Decision("hold", 0.0, 1.0, f"custom strategy: price not yet above {comparison} by {threshold_pct}%")

        if deviation <= -threshold:
            strength = min(1.0, max(0.0, abs(deviation) / max(threshold, 0.01)))
            return Decision(
                "sell",
                position_size,
                leverage,
                f"custom strategy: price below {comparison} by {threshold_pct}%",
                round(strength, 4),
                take_profit_pct,
                stop_loss_pct,
            )

        return Decision("hold", 0.0, 1.0, f"custom strategy: price not yet below {comparison} by {threshold_pct}%")

    STRATEGIES[strategy_id] = custom_strategy
    _registered_strategy_catalog[strategy_id] = {
        "id": strategy_id,
        "name": f"Custom {action.upper()} on {comparison.upper()}",
        "type": "structured",
        "description": f"Custom {action} signal using {comparison} comparison with a {threshold_pct}% threshold.",
    }


def build_signal_from_ticker(ticker: dict[str, Any], strategy_id: str | None = None) -> dict[str, Any]:
    selected_strategy_id = strategy_id or get_strategy_for_symbol(str(ticker.get("symbol", "")))
    decision = STRATEGIES[selected_strategy_id](ticker)
    decision = _apply_builtin_strategy_config(selected_strategy_id, decision)
    return decision_to_dict(decision)


def list_strategy_catalog() -> dict[str, dict[str, Any]]:
    return dict(_registered_strategy_catalog)
