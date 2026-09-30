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
import time
from getpass import getpass

import requests

BASE_URL = "https://api.bitget.com"
PATH = "/api/v2/mix/account/account"


def main() -> None:
    api_key = input("Bitget demo API key: ").strip()
    api_secret = getpass("Bitget demo API secret: ").strip()
    passphrase = getpass("Bitget demo API passphrase: ").strip()
    if not api_key or not api_secret or not passphrase:
        print("All three Bitget demo credential fields are required.")
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