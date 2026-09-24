from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def fetch_combined_balance_snapshot(execution_client: Any, market_service: Any) -> dict[str, Any] | None:
    futures = execution_client.fetch_futures_account_balance()
    spot = execution_client.fetch_spot_assets()
    if futures.get("status") == "not_configured" and spot.get("status") == "not_configured":
        return None

    assets = spot.get("assets", []) if spot.get("status") == "ok" else []
    usdt_asset = next(
        (asset for asset in assets if str(asset.get("coin", "")).upper() == "USDT"),
        {},
    )
    spot_equity = float(
        usdt_asset.get(
            "usdtBalance",
            usdt_asset.get("balance", usdt_asset.get("available", usdt_asset.get("availableBalance", 0))),
        )
        or 0
    )
    for asset in assets:
        coin = str(asset.get("coin", "")).upper()
        if not coin or coin == "USDT":
            continue
        quantity = float(asset.get("total", asset.get("available", asset.get("balance", 0))) or 0)
        if quantity <= 0:
            continue
        ticker = market_service.fetch_spot_ticker(f"{coin}USDT")
        if ticker.get("status") == "live":
            spot_equity += quantity * float(ticker.get("last_price", 0) or 0)

    futures_equity = float(futures.get("equity", 0) or 0) if futures.get("status") == "ok" else 0.0
    combined_equity = round(futures_equity + spot_equity, 4) if futures.get("status") == "ok" else round(spot_equity, 4)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "balance": combined_equity,
        "equity": combined_equity,
        "futures_equity": round(futures_equity, 4),
        "spot_equity": round(spot_equity, 4),
    }