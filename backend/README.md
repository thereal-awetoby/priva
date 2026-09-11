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
GET  /strategies
GET  /risk-settings
POST /risk-settings
POST /strategies/parse
POST /strategies/{strategy_id}/backtest
POST /risk-check
POST /paper-trade
GET  /kill-switch
POST /kill-switch
```

For a full close, send `position_side: "buy"` for a long or
`position_side: "sell"` for a short. Stop the agent before manually closing a
position so the loop cannot immediately open another one.

## Builder A integration notes

Builder A is intentionally kept separate from the backend work, but it can use
this backend as a clean API layer. The current live backend base URL is:

```text
https://priva-499h.onrender.com
```

Recommended Builder A workflow:

1. `GET /strategies` to fetch the available strategy catalog.
2. `POST /strategies/parse` with natural-language text to convert a user prompt
   into a structured strategy payload. Builder A should send `use_gemini: true`
   when it wants the provider-backed parser path; the backend handles the Gemini
   API key on the server side.
3. `GET /risk-settings` and `POST /risk-settings` to expose or update allowed
   symbols and risk limits.
4. `POST /risk-check` before submitting an order to validate a trade against the
   current risk engine state.
5. `POST /paper-trade` for execution in the Bitget paper environment.
6. `POST /strategies/{strategy_id}/backtest` to run a historical backtest and
   retrieve metrics.

Important Builder A guidance:

- Builder A should not collect or store provider API keys in the browser.
- All provider-backed parsing is server-side and uses the backend environment.
- The backend currently supports `use_gemini`, while older `use_qwen` / `use_grok`
  payloads are still tolerated for compatibility.

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
- Natural-language strategy parsing with strict validation
- Gemini-backed strategy parsing via the backend provider path
- Configurable risk/settings endpoints and allowed-symbol validation
- `POST /strategies/{id}/backtest` with shared metrics output
- `53` automated tests passing locally

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

1. Keep paper-trading logs running and prepare the final demo and submission.
2. Update Builder A to consume the verified backend API contract and display the
   live strategy, risk, and metrics responses.
3. Revisit any follow-up improvements after Builder A handoff, such as richer
   metrics visualization or additional strategy UX polish.

> Note: the core backend backlog is effectively complete. Builder A remains a
> separate frontend stream and should use the API contract documented above.