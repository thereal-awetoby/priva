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
- Two built-in strategies with a shared decision contract
- Supabase persistence for active strategy and per-process PnL sessions
- Regression tests for execution, risk, agent-loop, strategy, and metrics behavior

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

The supported tokenized-stock futures symbols are currently `AAPLUSDT` and
`TSLAUSDT`. `MSFTUSDT` is not recognized by the configured Bitget paper market
and must not be included in `AGENT_WATCHED_SYMBOLS`.

## Strategy system

Each active strategy returns the same decision shape consumed by risk checks and
execution:

```json
{
	"action": "buy",
	"size": 1.0,
	"leverage": 1.0,
	"reason": "...",
	"signal_strength": 0.5
}
```

Implemented strategies:

- `momentum_breakout` — compares current price with the opening price
- `mean_reversion` — fades moves at least 1% away from the opening price

Activate one with:

```bash
curl.exe -X POST \
	"https://YOUR-SERVICE.onrender.com/strategies/mean_reversion/activate" \
	| python -m json.tool
```

The selected strategy is persisted in Supabase and restored at startup. If
Supabase is not configured, activation remains process-local.

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

alter table public.agent_cycles
	add column if not exists session_id text;

create index if not exists agent_cycles_session_id_idx
	on public.agent_cycles (session_id);
```

The backend uses the singleton row `id = 'global'`. It loads that row at
startup and upserts it when `/strategies/{strategy_id}/activate` succeeds.
Each backend process also gets a `session_id`; realized PnL is calculated from
cycles in the current session, while unrealized PnL comes from live Bitget
positions.

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

- app/main.py — FastAPI routes and live dashboard calculations
- app/agent_loop.py — autonomous scheduler and live-position gate
- app/strategy.py — strategy registry and decision contract
- app/paper_execution.py — authenticated Bitget paper execution
- app/performance.py — session realized and live unrealized PnL calculations
- app/risk_engine.py — hard-rule risk checks
- app/supabase_logging.py — cycle and strategy persistence
- tests/ — regression coverage for the backend
- requirements.txt — Python dependencies
- render.yaml — Render deployment config

## Completed

- Render deployment and health/status endpoints
- Real Bitget market data for supported stock-futures symbols
- Paper futures opens with explicit leverage configuration
- Live Bitget position inspection with leverage and margin mode
- Full-position closing through Bitget flash-close
- Live unrealized PnL and risk usage
- Session-scoped realized PnL calculation
- Supabase cycle logging and encrypted intent hashes
- Live Bitget position checks in the autonomous loop
- Functional kill switch
- Functional built-in strategy activation
- Supabase persistence for the active strategy
- `43` automated tests passing locally

## Known limitations

- Partial position closes are intentionally unsupported.
- `/agent-cycle` evaluates a decision but does not submit an order; the
	autonomous loop and `/paper-trade` perform execution.
- The configured Bitget paper account supports AAPLUSDT and TSLAUSDT, not
	MSFTUSDT.
- Realized PnL is scoped to the current backend session. Historical cycles
	created before `session_id` was added are not used for the current session.
- Strategy persistence requires the Supabase migration and environment
	variables documented above.

## Remaining work

1. Build a reusable historical-candle backtester for both built-in strategies.
2. Add return, win rate, Sharpe ratio, and maximum drawdown metrics.
3. Add `POST /strategies/{id}/backtest` with a shared metrics response.
4. Add separate natural-language and structured-form strategy paths.
5. Add Grok JSON parsing and strict validation for natural-language strategies.
6. Add configurable risk/settings endpoints and allowed-symbol validation.
7. Add strategy and metrics views to the Builder A frontend.
8. Keep paper-trading logs running and prepare the final demo and submission.