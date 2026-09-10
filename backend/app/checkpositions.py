"""
Quick one-off script to check whether your Bitget account is in
one-way (single) or hedge (double) position mode.

Usage:
    python check_position_mode.py
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

import requests

BASE_URL = "https://api.bitget.com"
PATH = "/api/v2/mix/account/account"


def main() -> None:
    api_key = os.getenv("BITGET_API_KEY", "")
    api_secret = os.getenv("BITGET_API_SECRET", "")
    passphrase = os.getenv("BITGET_API_PASSPHRASE", "")

    missing = [
        name
        for name, val in [
            ("BITGET_API_KEY", api_key),
            ("BITGET_API_SECRET", api_secret),
            ("BITGET_API_PASSPHRASE", passphrase),
        ]
        if not val
    ]
    if missing:
        print(f"Missing env vars: {', '.join(missing)}")
        print("Set them in your shell before running this script, e.g.:")
        print('  export BITGET_API_KEY="..."')
        print('  export BITGET_API_SECRET="..."')
        print('  export BITGET_API_PASSPHRASE="..."')
        return

    query = "?symbol=AAPLUSDT&marginCoin=USDT&productType=USDT-FUTURES"
    timestamp = str(int(time.time() * 1000))
    prehash = timestamp + "GET" + PATH + query
    signature = base64.b64encode(
        hmac.new(api_secret.encode(), prehash.encode(), hashlib.sha256).digest()
    ).decode()

    headers = {
        "ACCESS-KEY": api_key,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": passphrase,
        "Content-Type": "application/json",
        # Include this if the credentials are for the paper/demo account.
        "paptrading": "1",
    }

    resp = requests.get(f"{BASE_URL}{PATH}{query}", headers=headers, timeout=15)
    try:
        payload = resp.json()
    except ValueError:
        print("Non-JSON response:", resp.status_code, resp.text)
        return

    print(json.dumps(payload, indent=2))

    pos_mode = (payload.get("data") or {}).get("posMode")
    if pos_mode:
        print(f"\n>>> posMode: {pos_mode}")
    else:
        print("\n>>> Could not find posMode in response (see raw output above).")


if __name__ == "__main__":
    main()