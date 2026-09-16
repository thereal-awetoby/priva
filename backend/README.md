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
- Built-in strategy config overrides for `position_size`, `leverage`, TP/SL, and threshold values
- `GET /pnl` metrics for `win_rate_pct` and `max_drawdown_pct`
- `GET /activity-log` metadata including `mode`
- Separate Autonomous and Strategy activity classification in cycle logs
- Spot/futures symbol normalization for risk allowlists
- Unsupported-symbol blocking before market-data or order processing
- Supabase persistence for active strategy and per-process PnL sessions
- Supabase bearer-token verification and encrypted per-user Bitget credential vault
- Authenticated `/auth/session`, connection, and manual trade routes
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
- http://127.0.0.1:8001/account/balance
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
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `PRIVA_AUTH_REQUIRED=true` to require Supabase sessions
- `PRIVA_CREDENTIAL_ENCRYPTION_KEY` (the output of `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)

The encryption key must be the generated 44-character URL-safe base64 value,
not the Python command itself. If the variable is missing or malformed, the
service still starts but credential connection and persistence remain disabled.

The client always sends Bitget's `paptrading: 1` header. Without all three
secrets, the route returns `not_configured` and does not call the exchange.

`GET /account/balance` reads the connected demo account's futures equity and
available USDT margin, plus spot USDT availability. It is read-only. Demo
funds must be added through Bitget's demo-trading interface or supported demo
funding workflow; normal trading API credentials cannot mint account balance.
The response also includes `starting_balance`, `daily_change`, and
`daily_change_pct`; the baseline is the first observed balance for the current
UTC day.

For the single-workspace demo, users can connect credentials through
`POST /connection/bitget`. The backend verifies them against Bitget before
using them for the authenticated user's execution client. Credentials are
never returned to the frontend or persisted in plaintext. `POST /connection/bitget/disconnect`
clears the runtime credentials. The backend now provides Supabase
authentication and an encrypted per-user runtime vault when the variables
above are configured.

Authenticated requests must include `Authorization: Bearer <Supabase access token>`.
The connection route verifies credentials with Bitget before encrypting them in
the per-user runtime vault. Secrets are never returned to the client.

User-scoped autonomous controls are available through:

```text
GET  /user/agent-loop
GET  /user/agent-settings
POST /user/agent-settings
```

These settings persist the selected strategy, per-symbol strategy assignments,
symbols, market, TP/SL rules, opposite-signal exits, and risk limits. The
authenticated worker restores them after a backend restart.

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

### Default strategy behavior

- `momentum_breakout`
  - compare `last_price` vs `open_price`
  - `buy` if price rose above the open, `sell` if price fell below the open, `hold` otherwise
  - default `size = 1.0` on active signals, `size = 0.0` on `hold`
   - adaptive futures leverage from `1.0x` to `3.0x` based on signal strength

- `mean_reversion`
  - compare `last_price` vs `open_price` and compute deviation `((last_price - open_price) / open_price)`
  - default threshold is `1%`
  - `sell` if deviation `>= 1%`, `buy` if deviation `<= -1%`, `hold` otherwise
  - default `size = 1.0` on active signals, `size = 0.0` on `hold`
   - adaptive futures leverage from `1.0x` to `3.0x` based on distance beyond the threshold

Built-in strategies choose leverage per trade using bounded confidence tiers:
weak signals use `1x`, medium signals use `2x`, and strong signals use `3x`.
Explicit strategy leverage overrides still take precedence, and the risk engine
rejects any trade above the configured `max_leverage`.

### Configurable builtin strategy overrides

The backend now accepts builtin strategy config overrides through the parse flow and stores them per strategy ID. Supported values are:

- `position_size` / `size`
- `leverage`
- `take_profit_pct` / `take_profit`
- `stop_loss_pct` / `stop_loss`
- `threshold_pct`

This means the same strategy fields Builder A may expose in a form can now be applied to prebuilt strategies as well as custom structured strategies.

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

The activation route also accepts an optional symbol selection. This updates
the running agent loop for the current backend process:

```bash
curl.exe -X POST \
   "https://YOUR-SERVICE.onrender.com/strategies/mean_reversion/activate" \
   -H "Content-Type: application/json" \
   -d '{"symbols":["AAPLUSDT","TSLAUSDT"]}' \
   | python -m json.tool
```

Only `AAPLUSDT` and `TSLAUSDT` are accepted. The selection is process-local
and resets to `AGENT_WATCHED_SYMBOLS` after a backend restart.

Built-in strategy activation can also receive per-strategy controls:

```json
{
   "symbols": ["AAPLUSDT", "TSLAUSDT"],
   "strategy_config": {
      "leverage": 2,
      "take_profit_pct": 4,
      "stop_loss_pct": 1
   }
}
```

The backend validates and applies these values to the selected built-in
strategy. Authenticated runtimes persist the configuration in
`user_agent_settings` and restore it after restart.

Different strategies can be assigned to different symbols in the same request:

```json
{
   "symbols": ["AAPLUSDT", "TSLAUSDT"],
   "strategy_by_symbol": {
      "AAPLUSDT": "momentum_breakout",
      "TSLAUSDT": "mean_reversion"
   }
}
```

Symbols without an assignment use the globally activated strategy.

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

For multi-user credential persistence and user-scoped cycle logs, also run
[`supabase_multi_user.sql`](supabase_multi_user.sql) once in the Supabase SQL
Editor. It creates the encrypted-credential and user-settings tables and adds
`user_id` to `agent_cycles`. The backend uses the service-role key server-side;
encrypted credentials must never be exposed through client policies.

The backend uses the singleton row `id = 'global'`. It loads that row at
startup and upserts it when `/strategies/{strategy_id}/activate` succeeds.
Each backend process also gets a `session_id`; realized PnL is calculated from
cycles in the current session, while unrealized PnL comes from live Bitget
positions.

## Useful endpoints

```text
GET  /health
GET  /strategies
GET  /agent-settings
POST /agent-settings
GET  /risk-settings
POST /risk-settings
POST /strategies/parse
POST /strategies/{strategy_id}/backtest
POST /risk-check
POST /paper-trade
GET  /kill-switch
POST /kill-switch
```

Autonomous execution defaults to USDT futures and can be switched at runtime
with `POST /agent-settings` using `{"market":"futures"}` or
`{"market":"spot"}`. The setting is process-local and resets to
`AGENT_MARKET_TYPE` (or futures) after restart.

The same endpoint controls autonomous exits. It defaults to a `5%` take-profit,
a `2%` stop-loss, and closing when the next signal opposes the open position:

```json
{
   "market": "futures",
   "take_profit_pct": 5,
   "stop_loss_pct": 2,
   "close_on_signal_violation": true
}
```

The agent evaluates these rules before adding to or opening a position. Futures
positions use Bitget flash-close; spot positions use an opposite market order.

## Activity, symbols, and history

Every agent cycle includes a `mode` value in its activity record:

- `autonomous` for the autonomous loop
- `strategy` when a selected built-in or custom strategy drives the cycle

The `/activity-log` response exposes this field so clients can keep the two
activity streams separate. Older records without `mode` are treated as
autonomous for compatibility.

Only `AAPLUSDT` and `TSLAUSDT` are supported paper symbols. The risk engine
normalizes base symbols and futures symbols, so an allowlist containing `AAPL`
matches a trade reported as `AAPLUSDT`. Unsupported symbols such as `MSFTUSDT`
are blocked before market data or execution and excluded from the activity
feed.

Supabase activity reads are paginated so exports are not limited to the old
100-record window. The in-memory fallback retains up to 1,000 recent cycles.

After applying the backend code, run `supabase_multi_user.sql` in Supabase so
`agent_cycles.mode` and `user_agent_settings.strategy_config` exist.

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
2. `POST /strategies/parse` with either natural-language text or a structured
   strategy payload. Builder A should send `use_gemini: true` when it wants the
   provider-backed parser path; the backend handles the Gemini API key on the
   server side.
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
- The `/strategies/parse` endpoint accepts either a `text` payload or a
  `strategy` payload.
- The currently verified structured builtin strategy payload shape includes
  `{"strategy": {"target_strategy": "mean_reversion", "position_size": 3.5, "leverage": 2.0, "take_profit_pct": 2.5, "stop_loss_pct": 1.25}}`.
  Builder A can also send `name` and `description` at the top level to preserve
  strategy metadata in the parse response.

## Risk settings defaults and current logic

The risk engine starts with the following defaults:

- `max_position_size = 25000`
- `max_daily_loss = 1500`
- `max_leverage = 5.0`
- `enabled = True`
- `allowed_symbols = None` unless explicitly configured

`POST /risk-settings` updates these values at runtime, and `GET /risk-settings`
returns the current live configuration. The engine enforces the same checks that
were described earlier: symbol allowlist, max position size, max daily loss,
max leverage, and aggregate same-symbol position size.

## Metrics already implemented

Yes — the earlier request for win rate and max drawdown was completed.

- `GET /pnl` now returns `win_rate_pct` and `max_drawdown_pct`
- `GET /activity-log` now includes `mode` metadata per entry

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
- Builtin strategy config overrides for position size, leverage, TP/SL, and threshold values
- Configurable risk/settings endpoints and allowed-symbol validation
- `POST /strategies/{id}/backtest` with shared metrics output
- `GET /pnl` returning `win_rate_pct` and `max_drawdown_pct`
- `GET /activity-log` including `mode` metadata
- `77` automated tests passing locally

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
- Credentials are encrypted in memory and persisted to Supabase when the
   multi-user migration and service-role configuration are present; without
   those, credentials are lost when Render restarts.
- Authenticated users receive separate runtime workers, Bitget clients, risk
   engines, settings, and user-filtered cycle logs. Remaining production work
   includes frontend adoption of the authenticated endpoints and user-scoping
   all legacy read-only dashboard routes.

## Remaining work

1. Keep paper-trading logs running and prepare the final demo and submission.
2. Update Builder A to consume the verified backend API contract and display the
   live strategy, risk, and metrics responses.
3. Revisit any follow-up improvements after Builder A handoff, such as richer
   metrics visualization or additional strategy UX polish.

> Note: the core backend backlog is effectively complete. Builder A remains a
> separate frontend stream and should use the API contract documented above.