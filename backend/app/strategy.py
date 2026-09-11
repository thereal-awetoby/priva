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

    return Decision(signal, 1.0 if signal != "hold" else 0.0, 1.0, "simple price-vs-open momentum signal", round(strength, 4))


def _mean_reversion_strategy(ticker: dict[str, Any]) -> Decision:
    if ticker.get("status") != "live":
        return Decision("hold", 0.0, 1.0, "market feed unavailable; fallback mode active")

    last_price = float(ticker.get("last_price", 0.0) or 0.0)
    open_price = float(ticker.get("open_price", 0.0) or 0.0)
    if last_price <= 0 or open_price <= 0:
        return Decision("hold", 0.0, 1.0, "invalid market prices")

    deviation = (last_price - open_price) / open_price
    if deviation >= 0.01:
        return Decision("sell", 1.0, 1.0, "mean reversion: price extended above open", round(min(1.0, deviation), 4))
    if deviation <= -0.01:
        return Decision("buy", 1.0, 1.0, "mean reversion: price extended below open", round(min(1.0, abs(deviation)), 4))
    return Decision("hold", 0.0, 1.0, "mean reversion: price within neutral band")


STRATEGIES = {
    "momentum_breakout": _momentum_strategy,
    "mean_reversion": _mean_reversion_strategy,
}
_active_strategy_id = "momentum_breakout"


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


def _parse_with_grok(text: str) -> dict[str, Any]:
    api_key = (
        os.getenv("GROK_API_KEY")
        or os.getenv("XAI_API_KEY")
        or os.getenv("QWEN_API_KEY")
        or os.getenv("DASHSCOPE_API_KEY")
    )
    if not api_key:
        raise ValueError("Grok API key is required. Set GROK_API_KEY or XAI_API_KEY.")

    base_url = (os.getenv("GROK_API_BASE_URL") or os.getenv("QWEN_API_BASE_URL") or "https://api.x.ai/v1").rstrip("/")
    model = os.getenv("GROK_MODEL") or os.getenv("QWEN_MODEL") or "grok-2-latest"

    response = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You convert a natural-language trading strategy into JSON. Return a JSON object only. "
                        "Supported object shapes: {\"kind\":\"builtin\",\"target_strategy\":\"mean_reversion\",\"threshold_pct\":1.0} "
                        "or {\"kind\":\"builtin\",\"target_strategy\":\"momentum_breakout\",\"threshold_pct\":1.0}."
                    ),
                },
                {"role": "user", "content": text},
            ],
            "temperature": 0,
        },
        timeout=30,
    )

    if response.status_code >= 400:
        raise ValueError(
            f"Grok parsing request failed with status {response.status_code}: {response.text}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise ValueError("Grok response was not valid JSON") from exc

    choices = payload.get("choices") or []
    if not choices or not isinstance(choices, list):
        raise ValueError("Grok response did not include any chat choices")

    message = choices[0].get("message", {})
    content = message.get("content")
    if not content:
        raise ValueError("Grok response did not include message content")

    parsed = _extract_json_from_content(content)

    if parsed.get("kind") == "builtin":
        if parsed.get("target_strategy") not in {"mean_reversion", "momentum_breakout"}:
            raise ValueError("Grok returned an unsupported builtin strategy")
        if parsed.get("threshold_pct") is None:
            raise ValueError("Grok response is missing threshold_pct")
        return parsed

    raise ValueError("Grok returned an unsupported strategy shape")


def parse_natural_language_strategy(
    text: str,
    *,
    use_grok: bool = False,
    use_qwen: bool | None = None,
) -> dict[str, Any]:
    normalized = (text or "").strip()
    if not normalized:
        raise ValueError("strategy text is required")

    if use_qwen is not None:
        use_grok = use_grok or use_qwen

    if use_grok:
        return _parse_with_grok(normalized)

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

    return {
        "kind": "custom",
        "action": action,
        "comparison": comparison,
        "threshold_pct": threshold_pct,
    }


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


def build_signal_from_ticker(ticker: dict[str, Any]) -> dict[str, Any]:
    return decision_to_dict(STRATEGIES[_active_strategy_id](ticker))
