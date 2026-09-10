# Priva Backend

FastAPI backend and autonomous paper-trading agent for Priva, a Bitget AI Base
Camp trading project for tokenized U.S. stock futures.

## What is included

- FastAPI API hosted on Render
- Bitget public market data for AAPLUSDT and TSLAUSDT
- Authenticated Bitget paper futures execution with `paptrading: 1`
- Autonomous five-minute agent loop with encrypted intent hashes
- Live Bitget positions, PnL, risk usage, and Supabase cycle logging
- Risk checks for position size, daily loss, and leverage
- Kill switch and full-position close via Bitget flash-close
- Regression tests for execution, risk, agent-loop, and metrics behavior

## Run locally

```bash
cd c:\Users\odusa\Desktop\Priva\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Then open:

- http://127.0.0.1:8001/health
- http://127.0.0.1:8001/status
- http://127.0.0.1:8001/positions
- http://127.0.0.1:8001/pnl
- http://127.0.0.1:8001/risk-usage
- http://127.0.0.1:8001/agent-loop
- http://127.0.0.1:8001/strategies

Run the tests from `backend/`:

```bash
python -m pytest -q
```

## Bitget paper execution

The `/paper-trade` route runs the risk engine first, sets the requested futures
leverage, then submits an authenticated spot or USDT-futures market order to
Bitget's paper environment. Configure these secrets in Render's environment settings:

- `BITGET_API_KEY`
- `BITGET_API_SECRET`
- `BITGET_API_PASSPHRASE`
- `BITGET_POSITION_MODE` (use `hedge` for the configured futures account)
- `AGENT_WATCHED_SYMBOLS` (use `AAPLUSDT,TSLAUSDT`)

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

New futures opens explicitly set the requested leverage before placing the order.
Full closes use Bitget's dedicated flash-close endpoint because the generic
`tradeSide: close` path is unreliable for these tokenized-stock futures. Partial
closes are currently rejected intentionally.

### Supabase strategy persistence

Run this once in the Supabase SQL editor to persist the active strategy across
Render restarts:

```sql
create table if not exists public.strategy_settings (
	id text primary key,
	strategy_id text not null,
	updated_at timestamptz not null default now()
);

alter table public.strategy_settings enable row level security;
```

The backend uses the singleton row `id = 'global'`. It loads that row at
startup and upserts it when `/strategies/{strategy_id}/activate` succeeds.

## Useful endpoints

```text
GET  /health
GET  /agent-loop
GET  /market-data?symbol=AAPLUSDT
GET  /positions
GET  /pnl
GET  /risk-usage
GET  /activity-log
POST /paper-trade
POST /positions/{symbol}/close
GET  /kill-switch
POST /kill-switch
```

For a full close, send `position_side: "buy"` for a long or
`position_side: "sell"` for a short. Stop the agent before manually closing a
position so the loop cannot immediately open another one.

## Main files

- app/main.py — FastAPI app and mock API routes
- requirements.txt — Python dependencies
- render.yaml — Render deployment config

## Current status

The live paper-trading path is operational: market data, risk checks, leverage
configuration, order submission, live positions, PnL, risk usage, Supabase
logging, kill switch, and full-position closing are implemented. Remaining
hackathon work includes strategy backtesting and activation, configurable risk
settings, final performance metrics, documentation polish, and maintaining the
paper-trading log through submission.
