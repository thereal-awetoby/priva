from __future__ import annotations

from dataclasses import asdict, dataclass
from math import sqrt
from typing import Any, Literal


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
