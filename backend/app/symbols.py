from __future__ import annotations

SPOT_SYMBOL_MAP = {
    "AAPLUSDT": "RAAPLUSDT",
    "TSLAUSDT": "RTSLAUSDT",
}


def spot_symbol(symbol: str) -> str:
    logical_symbol = str(symbol).upper()
    return SPOT_SYMBOL_MAP.get(logical_symbol, logical_symbol)


def logical_symbol(symbol: str) -> str:
    exchange_symbol = str(symbol).upper()
    for logical, mapped in SPOT_SYMBOL_MAP.items():
        if mapped == exchange_symbol:
            return logical
    return exchange_symbol
