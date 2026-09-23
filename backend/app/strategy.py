from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, replace
from math import sqrt
from typing import Any, Literal

import requests

MAX_LEVERAGE = 3.0


@dataclass(frozen=True)
class Decision:
    action: Literal["buy", "sell", "hold"]
    size: float
    leverage: float
    reason: str
    signal_strength: float = 0.0
    take_profit_pct: float | None = None
    stop_loss_pct: float | None = None
    market: Literal["spot", "futures"] | None = None
    trailing_profit_trigger_usd: float | None = None
    trailing_profit_floor_usd: float | None = None
    trailing_profit_lock_pct: float | None = None


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
    if last_price <= 0 or open_price <= 0:
        return Decision("hold", 0.0, 1.0, "invalid market prices")
    config = _get_builtin_strategy_config("momentum_breakout")
    threshold_pct = float(config.get("threshold_pct", 1.0) or 1.0)
    threshold = threshold_pct / 100.0
    if last_price > open_price and (last_price - open_price) / open_price >= threshold:
        signal = "buy"
        move = (last_price - open_price) / open_price
        strength = min(1.0, max(0.0, move / max(threshold * 4, 0.01)))
    elif last_price < open_price and (open_price - last_price) / open_price >= threshold:
        signal = "sell"
        move = (open_price - last_price) / open_price
        strength = min(1.0, max(0.0, move / max(threshold * 4, 0.01)))
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


def _overnight_gap_strategy(ticker: dict[str, Any]) -> Decision:
    if ticker.get("status") != "live":
        return Decision("hold", 0.0, 1.0, "market feed unavailable; fallback mode active")

    last_price = float(ticker.get("last_price", 0.0) or 0.0)
    previous_close = float(ticker.get("previous_close", 0.0) or 0.0)
    session_open = float(ticker.get("session_open", 0.0) or 0.0)
    if last_price <= 0 or previous_close <= 0 or session_open <= 0:
        return Decision("hold", 0.0, 1.0, "overnight gap data unavailable")

    config = _get_builtin_strategy_config("overnight_gap")
    threshold_pct = float(config.get("threshold_pct", 1.0) or 1.0)
    gap_pct = ((session_open - previous_close) / previous_close) * 100
    strength = min(1.0, abs(gap_pct) / max(threshold_pct, 0.01))
    leverage_signal = min(1.0, abs(gap_pct) / max(threshold_pct * 4, 0.01))
    if gap_pct >= threshold_pct:
        return Decision("sell", 1.0, _adaptive_leverage(leverage_signal), f"overnight gap: open {gap_pct:.2f}% above previous close", round(strength, 4))
    if gap_pct <= -threshold_pct:
        return Decision("buy", 1.0, _adaptive_leverage(leverage_signal), f"overnight gap: open {abs(gap_pct):.2f}% below previous close", round(strength, 4))
    return Decision("hold", 0.0, 1.0, f"overnight gap: {gap_pct:.2f}% within threshold", 0.0)


def _pairs_strategy_placeholder(ticker: dict[str, Any]) -> Decision:
    return Decision("hold", 0.0, 1.0, "pairs trading requires the two-symbol cycle")


def build_pairs_signal(
    first_symbol: str,
    second_symbol: str,
    first_closes: list[float],
    second_closes: list[float],
    *,
    entry_zscore: float = 2.0,
    exit_zscore: float = 0.5,
) -> dict[str, Any]:
    """Build a market-neutral signal from the log-price spread of two symbols."""
    paired = [(float(first), float(second)) for first, second in zip(first_closes, second_closes) if first > 0 and second > 0]
    if len(paired) < 3:
        return {"action": "hold", "status": "logged", "reason": "pairs strategy needs at least three aligned closes", "legs": []}

    spreads = [__import__("math").log(first) - __import__("math").log(second) for first, second in paired]
    current_spread = spreads[-1]
    history = spreads[:-1]
    mean = _safe_mean(history)
    std = _safe_std(history)
    if std <= 0:
        return {"action": "hold", "status": "logged", "reason": "pairs spread has no measurable variance", "legs": [], "spread": current_spread, "zscore": 0.0}

    zscore = (current_spread - mean) / std
    legs: list[dict[str, Any]] = []
    if zscore >= entry_zscore:
        legs = [{"symbol": first_symbol.upper(), "side": "sell"}, {"symbol": second_symbol.upper(), "side": "buy"}]
        action = "enter_pair"
        reason = "pairs spread is above its rolling mean"
    elif zscore <= -entry_zscore:
        legs = [{"symbol": first_symbol.upper(), "side": "buy"}, {"symbol": second_symbol.upper(), "side": "sell"}]
        action = "enter_pair"
        reason = "pairs spread is below its rolling mean"
    elif abs(zscore) <= exit_zscore:
        action = "exit_pair"
        reason = "pairs spread reverted toward its rolling mean"
    else:
        action = "hold"
        reason = "pairs spread is between entry and exit thresholds"

    return {
        "action": action,
        "status": "logged",
        "reason": reason,
        "legs": legs,
        "spread": round(current_spread, 8),
        "spread_mean": round(mean, 8),
        "spread_std": round(std, 8),
        "zscore": round(zscore, 4),
    }


STRATEGY_CATALOG = {
    "momentum_breakout": {
        "id": "momentum_breakout",
        "name": "Momentum Breakout",
        "type": "prebuilt",
        "description": "Trade price moves above or below the opening price after the configured threshold.",
    },
    "mean_reversion": {
        "id": "mean_reversion",
        "name": "Mean Reversion",
        "type": "prebuilt",
        "description": "Fade moves that extend at least 1% away from the opening price.",
    },
    "overnight_gap": {
        "id": "overnight_gap",
        "name": "Overnight Gap",
        "type": "prebuilt",
        "description": "Fade a sufficiently large gap between yesterday's close and today's open.",
    },
    "pairs_trading": {
        "id": "pairs_trading",
        "name": "Pairs Trading",
        "type": "prebuilt",
        "description": "Trade the mean reversion of the AAPL/TSLA log-price spread.",
    },
}

STRATEGIES = {
    "momentum_breakout": _momentum_strategy,
    "mean_reversion": _mean_reversion_strategy,
    "overnight_gap": _overnight_gap_strategy,
    "pairs_trading": _pairs_strategy_placeholder,
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
    market = config.get("market", decision.market)
    if market == "spot":
        leverage = 1.0

    return Decision(
        action=decision.action,
        size=size if decision.action in {"buy", "sell"} else decision.size,
        leverage=leverage if decision.action in {"buy", "sell"} else decision.leverage,
        reason=decision.reason,
        signal_strength=decision.signal_strength,
        take_profit_pct=take_profit_pct,
        stop_loss_pct=stop_loss_pct,
        market=market,
        trailing_profit_trigger_usd=decision.trailing_profit_trigger_usd,
        trailing_profit_floor_usd=decision.trailing_profit_floor_usd,
        trailing_profit_lock_pct=decision.trailing_profit_lock_pct,
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
        if normalized["threshold_pct"] <= 0:
            raise ValueError("strategy threshold_pct must be greater than zero")

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
            if normalized[field] > MAX_LEVERAGE:
                raise ValueError(f"strategy {field} must not exceed {MAX_LEVERAGE:g}x")

    for field in ("take_profit_pct", "take_profit", "stop_loss_pct", "stop_loss"):
        if field in config and config[field] is not None:
            try:
                value = float(config[field])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"strategy {field} must be numeric") from exc
            if value <= 0 or value > 100:
                raise ValueError(f"strategy {field} must be between 0 and 100")
            normalized[field.replace("take_profit", "take_profit_pct").replace("stop_loss", "stop_loss_pct")] = value

    if "market" in config:
        market = str(config["market"]).strip().lower()
        if market not in {"spot", "futures"}:
            raise ValueError("strategy market must be spot or futures")
        normalized["market"] = market

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
    if strategy_id in {"overnight_gap", "pairs_trading"}:
        raise ValueError(f"{strategy_id} is not backtestable with single-symbol candles")
    if not candles:
        raise ValueError("candles are required")

    initial_capital = max(float(initial_capital or 0.0), 0.0)
    if initial_capital <= 0:
        raise ValueError("initial_capital must be greater than zero")

    realized_pnl = 0.0
    position: dict[str, Any] | None = None
    closed_trades: list[dict[str, Any]] = []
    equity_curve = [initial_capital]
    last_valid_price: float | None = None

    for candle in candles:
        price = _price_from_candle(candle)
        if price <= 0:
            mark_price = last_valid_price if last_valid_price is not None else 0.0
            equity_curve.append(initial_capital + realized_pnl + (_position_pnl(position, mark_price) if position else 0.0))
            continue
        last_valid_price = price
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
                "qty": initial_capital / price,
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
                "qty": initial_capital / price,
            }

        current_equity = initial_capital + realized_pnl + (_position_pnl(position, price) if position else 0.0)
        equity_curve.append(current_equity)

    if position is not None and last_valid_price is not None:
        close_pnl = _position_pnl(position, last_valid_price)
        realized_pnl += close_pnl
        closed_trades.append(
            {
                "side": position["side"],
                "entry_price": position["entry_price"],
                "exit_price": last_valid_price,
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

    deflated_sharpe_ratio = 0.0
    if period_returns:
        adjustment = sqrt(len(period_returns) / 2.0)
        deflated_sharpe_ratio = sharpe_ratio - (adjustment * 0.35)

    return {
        "strategy_id": strategy_id,
        "status": "completed",
        "candles_analyzed": len(candles),
        "metrics": {
            "return": round(total_return, 4),
            "win_rate": round(win_rate, 4),
            "sharpe_ratio": round(sharpe_ratio, 4),
            "deflated_sharpe_ratio": round(deflated_sharpe_ratio, 4),
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
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Gemini API key is required. Set GEMINI_API_KEY or GOOGLE_API_KEY.")

    base_url = (os.getenv("GEMINI_API_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    model = os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"

    response = requests.post(
        f"{base_url}/models/{model}:generateContent",
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        json={
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "You convert a natural-language trading strategy into JSON. Return a JSON object only. "
                                "Supported object shapes: {\"kind\":\"builtin\",\"target_strategy\":\"mean_reversion\",\"threshold_pct\":1.0}, "
                                "{\"kind\":\"builtin\",\"target_strategy\":\"momentum_breakout\",\"threshold_pct\":1.0}, or "
                                "{\"kind\":\"builtin\",\"target_strategy\":\"overnight_gap\",\"threshold_pct\":1.0}.\n\n"
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
        if parsed.get("target_strategy") not in STRATEGIES:
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

    if "overnight gap" in lowered or "gap up" in lowered or "gap down" in lowered:
        return {
            "kind": "builtin",
            "target_strategy": "overnight_gap",
            "threshold_pct": threshold_pct,
            "raw_text": normalized,
        }

    if "pairs" in lowered or "spread" in lowered:
        return {
            "kind": "builtin",
            "target_strategy": "pairs_trading",
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
        if threshold_pct is not None and threshold_pct <= 0:
            raise ValueError("structured strategy threshold_pct must be greater than zero")

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
        if leverage > MAX_LEVERAGE:
            raise ValueError(f"structured strategy leverage must not exceed {MAX_LEVERAGE:g}x")

        take_profit_pct = payload.get("take_profit_pct", payload.get("take_profit"))
        stop_loss_pct = payload.get("stop_loss_pct", payload.get("stop_loss"))
        market = payload.get("market")
        if market is not None:
            market = str(market).strip().lower()
            if market not in {"spot", "futures"}:
                raise ValueError("structured strategy market must be spot or futures")

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
            stop_loss_pct = float(stop_loss_pct)
            if stop_loss_pct <= 0 or stop_loss_pct > 100:
                raise ValueError("structured strategy stop_loss_pct must be between 0 and 100")
            result["stop_loss_pct"] = stop_loss_pct
        if take_profit_pct is not None:
            take_profit_pct = float(take_profit_pct)
            if take_profit_pct <= 0 or take_profit_pct > 100:
                raise ValueError("structured strategy take_profit_pct must be between 0 and 100")
            result["take_profit_pct"] = take_profit_pct
        if market is not None:
            result["market"] = market
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
    if threshold_pct <= 0:
        raise ValueError("structured strategy threshold_pct must be greater than zero")

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
    if leverage > MAX_LEVERAGE:
        raise ValueError(f"structured strategy leverage must not exceed {MAX_LEVERAGE:g}x")

    take_profit_pct = payload.get("take_profit_pct", payload.get("take_profit"))
    stop_loss_pct = payload.get("stop_loss_pct", payload.get("stop_loss"))
    trailing_profit_trigger_usd = payload.get("trailing_profit_trigger_usd")
    trailing_profit_floor_usd = payload.get("trailing_profit_floor_usd")
    trailing_profit_lock_pct = payload.get("trailing_profit_lock_pct")
    if trailing_profit_trigger_usd is not None or trailing_profit_floor_usd is not None:
        if trailing_profit_trigger_usd is None or trailing_profit_floor_usd is None:
            raise ValueError("trailing profit trigger and floor must be provided together")
        try:
            trailing_profit_trigger_usd = float(trailing_profit_trigger_usd)
            trailing_profit_floor_usd = float(trailing_profit_floor_usd)
        except (TypeError, ValueError) as exc:
            raise ValueError("trailing profit values must be numeric") from exc
        if trailing_profit_trigger_usd <= 0 or trailing_profit_floor_usd <= 0:
            raise ValueError("trailing profit values must be greater than zero")
        if trailing_profit_floor_usd >= trailing_profit_trigger_usd:
            raise ValueError("trailing profit floor must be below its trigger")
    market = payload.get("market")
    if market is not None:
        market = str(market).strip().lower()
        if market not in {"spot", "futures"}:
            raise ValueError("structured strategy market must be spot or futures")

    for field_name, field_value in (("take_profit_pct", take_profit_pct), ("stop_loss_pct", stop_loss_pct)):
        if field_value is not None:
            try:
                numeric_value = float(field_value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"structured strategy {field_name} must be numeric") from exc
            if numeric_value <= 0 or numeric_value > 100:
                raise ValueError(f"structured strategy {field_name} must be between 0 and 100")

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
    if trailing_profit_trigger_usd is not None:
        result["trailing_profit_trigger_usd"] = trailing_profit_trigger_usd
        result["trailing_profit_floor_usd"] = trailing_profit_floor_usd
    if trailing_profit_lock_pct is not None:
        try:
            trailing_profit_lock_pct = float(trailing_profit_lock_pct)
        except (TypeError, ValueError) as exc:
            raise ValueError("trailing_profit_lock_pct must be numeric") from exc
        if trailing_profit_lock_pct <= 0 or trailing_profit_lock_pct >= 100:
            raise ValueError("trailing_profit_lock_pct must be between 0 and 100")
        result["trailing_profit_lock_pct"] = trailing_profit_lock_pct
    if market is not None:
        result["market"] = market
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


def register_custom_strategy(
    strategy_id: str,
    parsed_strategy: dict[str, Any],
    *,
    name: str | None = None,
    description: str | None = None,
) -> None:
    strategy_type = str(parsed_strategy.get("kind", "custom")).lower()
    if strategy_type != "custom":
        return

    action = str(parsed_strategy.get("action", "buy")).lower()
    comparison = str(parsed_strategy.get("comparison", "open")).lower()
    threshold_pct = float(parsed_strategy.get("threshold_pct", 0.0) or 0.0)
    if threshold_pct <= 0:
        raise ValueError("custom strategy threshold_pct must be greater than zero")
    position_size = float(parsed_strategy.get("position_size", parsed_strategy.get("size", 1.0)) or 1.0)
    leverage = float(parsed_strategy.get("leverage", 1.0) or 1.0)
    if leverage <= 0 or leverage > MAX_LEVERAGE:
        raise ValueError(f"custom strategy leverage must be between 0 and {MAX_LEVERAGE:g}")
    take_profit_pct = parsed_strategy.get("take_profit_pct")
    stop_loss_pct = parsed_strategy.get("stop_loss_pct")
    for field_name, field_value in (("take_profit_pct", take_profit_pct), ("stop_loss_pct", stop_loss_pct)):
        if field_value is not None and (float(field_value) <= 0 or float(field_value) > 100):
            raise ValueError(f"custom strategy {field_name} must be between 0 and 100")
    trailing_profit_trigger_usd = parsed_strategy.get("trailing_profit_trigger_usd")
    trailing_profit_floor_usd = parsed_strategy.get("trailing_profit_floor_usd")
    trailing_profit_lock_pct = parsed_strategy.get("trailing_profit_lock_pct")
    market = parsed_strategy.get("market")

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
                    market,
                    trailing_profit_trigger_usd=trailing_profit_trigger_usd,
                    trailing_profit_floor_usd=trailing_profit_floor_usd,
                    trailing_profit_lock_pct=trailing_profit_lock_pct,
                )
            return Decision(
                action="hold", size=0.0, leverage=1.0,
                reason=f"custom strategy: price not yet above {comparison} by {threshold_pct}%",
                take_profit_pct=take_profit_pct, stop_loss_pct=stop_loss_pct, market=market,
                trailing_profit_trigger_usd=trailing_profit_trigger_usd,
                trailing_profit_floor_usd=trailing_profit_floor_usd,
                trailing_profit_lock_pct=trailing_profit_lock_pct,
            )

        if deviation <= -threshold:
            strength = min(1.0, max(0.0, abs(deviation) / max(threshold, 0.01)))
            return Decision(
                action="sell", size=position_size, leverage=leverage,
                reason=f"custom strategy: price below {comparison} by {threshold_pct}%",
                signal_strength=round(strength, 4),
                take_profit_pct=take_profit_pct, stop_loss_pct=stop_loss_pct, market=market,
                trailing_profit_trigger_usd=trailing_profit_trigger_usd,
                trailing_profit_floor_usd=trailing_profit_floor_usd,
                trailing_profit_lock_pct=trailing_profit_lock_pct,
            )

        return Decision(
            action="hold", size=0.0, leverage=1.0,
            reason=f"custom strategy: price not yet below {comparison} by {threshold_pct}%",
            take_profit_pct=take_profit_pct, stop_loss_pct=stop_loss_pct, market=market,
            trailing_profit_trigger_usd=trailing_profit_trigger_usd,
            trailing_profit_floor_usd=trailing_profit_floor_usd,
            trailing_profit_lock_pct=trailing_profit_lock_pct,
        )

    STRATEGIES[strategy_id] = custom_strategy
    _registered_strategy_catalog[strategy_id] = {
        "id": strategy_id,
        "name": name or f"Custom {action.upper()} on {comparison.upper()}",
        "type": "structured",
        "description": description or f"Custom {action} signal using {comparison} comparison with a {threshold_pct}% threshold.",
    }


def unregister_custom_strategy(strategy_id: str) -> bool:
    definition = _registered_strategy_catalog.get(strategy_id)
    if not definition or definition.get("type") != "structured":
        return False
    STRATEGIES.pop(strategy_id, None)
    _registered_strategy_catalog.pop(strategy_id, None)
    for symbol, mapped_strategy_id in list(_symbol_strategy_ids.items()):
        if mapped_strategy_id == strategy_id:
            del _symbol_strategy_ids[symbol]
    if _active_strategy_id == strategy_id:
        activate_strategy("momentum_breakout")
    return True


def build_signal_from_ticker(ticker: dict[str, Any], strategy_id: str | None = None) -> dict[str, Any]:
    selected_strategy_id = strategy_id or get_strategy_for_symbol(str(ticker.get("symbol", "")))
    decision = STRATEGIES[selected_strategy_id](ticker)
    decision = _apply_builtin_strategy_config(selected_strategy_id, decision)
    if decision.market is None:
        decision = replace(
            decision,
            market="futures" if decision.action == "sell" or decision.leverage > 1 else "spot",
        )
    if decision.market == "spot":
        decision = replace(decision, leverage=1.0)
    return decision_to_dict(decision)


def list_strategy_catalog() -> dict[str, dict[str, Any]]:
    return dict(_registered_strategy_catalog)
