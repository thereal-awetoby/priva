# Priva Backend

This is the Builder B backend starter for the Priva hackathon project.

## What is included

- FastAPI app scaffold
- Basic health and status endpoints
- Mock data for positions, PnL, risk usage, activity log, strategies, and kill switch
- Render deployment config for a free-tier backend

## Run locally

```bash
cd c:\Users\odusa\Desktop\Priva
C:/Users/odusa/anaconda3/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Then open:

- http://127.0.0.1:8001/health
- http://127.0.0.1:8001/status
- http://127.0.0.1:8001/positions
- http://127.0.0.1:8001/strategies

## Bitget paper execution

The `/paper-trade` route runs the risk engine first, then submits an authenticated
spot or USDT-futures market order to Bitget's paper environment. Configure these secrets
in Render's environment settings:

- `BITGET_API_KEY`
- `BITGET_API_SECRET`
- `BITGET_API_PASSPHRASE`

The client always sends Bitget's `paptrading: 1` header. Without all three
secrets, the route returns `not_configured` and does not call the exchange.

Example request:

```bash
curl -s -X POST "https://YOUR-SERVICE.onrender.com/paper-trade" \
	-H "Content-Type: application/json" \
	-d '{"symbol":"AAPLUSDT","side":"buy","qty":5,"entry_price":320.06,"leverage":1,"market":"futures"}' \
	| python -m json.tool
```

Successful exchange submission returns `status: "submitted"` and a Bitget
`order_id`. The risk engine rejects an order before any exchange request is made.

## Main files

- app/main.py — FastAPI app and mock API routes
- requirements.txt — Python dependencies
- render.yaml — Render deployment config

## Current status

This matches the Day 1 milestone from the project brief: the app is live as a backend skeleton with mock data, ready for real market-data and paper-trading work next.
