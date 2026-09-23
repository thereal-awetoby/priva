# PRIVA SESSION HANDOFF
Date: 2026-09-22

## Latest Update: 2026-09-23

### Current Production State

- Render backend is live at `https://priva-499h.onrender.com`.
- Authenticated `/user/agent-loop` confirmed `running: true` with no worker errors.
- Supabase logging is configured and the latest persistence status is `logged`.
- All four execution profiles are currently running:
  - `autonomous:futures`
  - `autonomous:spot`
  - `strategy:futures`
  - `strategy:spot`
- Current symbols are `AAPLUSDT` and `TSLAUSDT`.
- Current exit settings are take profit `5%` and stop loss `2%`.
- `skipped_existing_position` means a worker detected an existing position and correctly avoided adding a conflicting trade.

### Multi-Worker Implementation

- User runtimes now support independent workers for each selected mode/market combination.
- The dashboard Control Center supports selecting Spot, Futures, Autonomous, and Strategy independently.
- Profile selection persists through `POST /user/execution-settings` as `execution_profiles`.
- The runtime keeps separate risk-engine instances per worker while sharing the authenticated Bitget client and cycle logger.
- Legacy single-market settings fall back to `autonomous:futures` or the previously selected strategy profile.
- Profile changes from synchronous FastAPI endpoints are marshalled onto the runtime's owning asyncio event loop.

### Deployment Fixes

- Fixed startup failure caused by calling `normalize_profiles` on `UserRuntimeRegistry` instead of `UserRuntime`.
- Fixed runtime reconfiguration failure: `RuntimeError: no running event loop`.
- Fixed the related `UserRuntime._run_worker was never awaited` warning.
- Render deployment subsequently reached `Application startup complete` and served authenticated dashboard requests successfully.

### Required Database Migration

- Run `backend/add_execution_profiles.sql` once in the Supabase SQL Editor for existing deployments.
- The complete schema migration also includes the `execution_profiles` column in `backend/supabase_multi_user.sql`.

### Current Validation

- Focused agent-loop suite: 24 passed.
- Spot position-gating and Supabase logger suite: 34 passed after the market-isolation fix below.
- Python compilation and static diagnostics passed for the runtime and API changes.
- Frontend ESLint passed after adding the multi-select controls.
- No GitHub push or commit was made automatically.

### Superseding UI Notes

- `Import history` and `Reset session` were removed from the dashboard top bar as requested.
- The current dashboard uses the Control Center market/mode selectors instead of a single Spot/Futures selector.

### Spot Execution Follow-up: 2026-09-23

- Root cause found for Spot workers reporting `skipped_existing_position`: the fallback Supabase query checked only symbol and status, so a submitted Futures cycle could be mistaken for an open Spot position.
- Fixed `SupabaseCycleLogger.has_open_position()` to accept and filter by market.
- Spot and Futures position gates now pass their selected market into the fallback query.
- Focused validation passed: 34 tests.
- Deploy the backend patch before expecting new Spot orders. After deployment, verify `/user/agent-loop` and look for a Spot worker cycle with `last_cycle_status: "submitted"` or a persisted activity record with `market: "spot"`.

## Session Purpose

Diagnose the worker error, repair Supabase persistence, backfill Bitget history from September 17 through September 22, correct activity/P&L presentation, and prepare a clean P&L reset workflow.

## Confirmed Live State

- Render backend: `https://priva-499h.onrender.com`
- Bitget account connection works.
- Bitget futures position mode: hedge.
- AAPLUSDT and TSLAUSDT positions were visible from Bitget.
- Worker status was confirmed `running: true`.
- Supabase cycle persistence was eventually confirmed `logged`.
- Spot USDT balance is now displayed from Bitget's `available` field.

## Root Causes Found

1. The UI displayed `worker error` when `last_persistence_status` was only a logging error. The worker itself was still running.
2. Authenticated startup queried Supabase with the local sentinel `local-development`, causing UUID error `22P02`.
3. `agent_cycles` was missing the `market` column, causing Supabase error `PGRST204`.
4. Bitget fills returned `data.fillList`, but the importer assumed `data` was a list and crashed with `AttributeError: 'str' object has no attribute 'get'`.
5. Activity views displayed signals as `Logged` or plain buy/sell even when orders were skipped or rejected.
6. Runtime close records stored the position entry price in a field later interpreted as the exit price, which could turn a loss into an incorrect gain.
7. Old offline history was mixed into reconstructed P&L even though activity may have happened outside Priva while the worker was stopped.

## Backend Changes

### `backend/app/main.py`

- Removed authenticated startup restoration using `restore_custom_strategies("local-development")`.
- Restored local-development strategies only when authenticated mode is disabled.
- Added response-body diagnostics for Supabase cycle logging in `supabase_logging.py` rather than hiding schema errors.
- Added `market` to the agent-cycle Supabase migration contract.
- Added Bitget history backfill endpoint already used by the UI: `POST /user/backfill-trades`.
- Backfill records use `mode = "autonomous"` for the one-time offline history.
- Normalized imported fill data and preserved Bitget-reported realized P&L fields when available (`profit`, `realizedPnl`, `realizedPL`, or `pnl`).
- Added `exit_price` handling for runtime close records.
- Closed activity records are exposed as `action = "close"`.
- Added `pnl_reset_at` support and filtering so activity/P&L can start from a clean reset boundary.
- Added confirmed endpoint `POST /user/reset-trading-session`:
  - Requires `{ "confirm": true }`.
  - Stops the user worker.
  - Reads all live futures positions.
  - Attempts to close every position through Bitget.
  - Refuses to persist the reset if any close fails.
  - Saves `pnl_reset_at`.
  - Restarts the worker.
- Updated account-balance normalization so Spot USDT uses `available`/`availableBalance` when `usdtBalance` and `balance` are absent.
- P&L reconstruction now excludes offline records marked with `ticker.status = "historical"` rather than inventing profit/loss from uncertain prices.
- Explicit exchange-reported realized P&L is used when present.

### `backend/app/agent_loop.py`

- Runtime closes now store both the original position `entry_price` and the actual market `exit_price`.

### `backend/app/performance.py`

- Realized P&L uses `exit_price` for live Priva-managed closes.
- Historical offline cycles are excluded from reconstructed realized and unrealized P&L.
- Explicit exchange-reported P&L takes precedence when available.

### `backend/app/paper_execution.py`

- Bitget fill response normalization supports nested `data.fillList`, nested `data.fills`, and list responses.

### `backend/app/supabase_logging.py`

- Supabase cycle-write failures now include the response body in logs, exposing errors such as missing columns.

## Tests Added or Updated

- `backend/tests/test_paper_execution.py`
  - Added nested Bitget `fillList` response regression coverage.
- `backend/tests/test_agent_loop.py`
  - Updated close P&L coverage to verify a losing close subtracts from realized P&L.
- `backend/tests/test_metrics_endpoints.py`
  - Added coverage that closed activity is labeled `close`.

Static diagnostics passed for touched Python and TypeScript files. Frontend ESLint passed when invoked through the local ESLint binary; some terminal attempts failed only because PowerShell PATH/execution-policy state changed during the session.

## Frontend Changes

### `priva-web/components/app/AppShell.tsx`

- Worker diagnostic no longer displays the signed-in email/user identifier.
- Persistence errors display as `logging error`, not `worker error`.
- Added `Reset session` button with browser confirmation.
- Reset action calls `POST /user/reset-trading-session` and reports the number of positions closed.

### `priva-web/components/app/panels/ActivityPanel.tsx`

- Activity rows now distinguish:
  - `Executed`
  - `Skipped: position already open`
  - `Rejected by exchange`
  - `Rejected by risk check`
  - `Signal logged`

### `priva-web/components/app/panels/ControlCenterPanel.tsx`

- Removed the separate Imported activity tab.
- One-time backfilled records appear as Autonomous activity.
- Recent activity and dashboard metrics refresh every 30 seconds instead of every six hours.
- Activity rows show the execution outcome.

## Supabase Files and Required SQL

### `backend/supabase_multi_user.sql`

Migration now adds:

- `agent_cycles.market`
- `user_agent_settings.pnl_reset_at`

Run the complete migration in Supabase SQL Editor if it has not already been applied.

### `backend/backfill_autonomous_history_2026-09-22.sql`

One-time repair script:

- Converts existing `mode = 'imported'` records from Sep 17 through Sep 22 to `mode = 'autonomous'`.
- Repairs old runtime close records by adding `order_result.exit_price` from the recorded live ticker when missing.
- Does not alter offline records with `ticker.status = 'historical'`.

Run this only as the historical cleanup/reset preparation step. The reset endpoint is the preferred clean-slate boundary going forward.

## Current Accounting Rules

- `Total P&L = Realized P&L + Unrealized P&L`.
- Live Bitget equity remains authoritative for account balance because it includes fees, funding, and activity outside Priva.
- Live Priva-managed closes use explicit entry and exit prices.
- Offline historical records are shown as activity but do not contribute guessed P&L.
- After `Reset session`, only records created at or after `pnl_reset_at` are considered by activity/P&L endpoints.
- A losing close subtracts from realized P&L; a winning close adds to it.

## Clean-Slate Procedure

1. Apply `backend/supabase_multi_user.sql` in Supabase.
2. Deploy backend and frontend changes.
3. Open the dashboard and click `Reset session`.
4. Confirm the warning. The endpoint closes all live futures positions before saving the reset boundary.
5. Verify positions are empty and the new P&L starts from zero/open activity.
6. Do not use the old history to judge the new session's P&L.

No reset was executed automatically during this session. The user must explicitly confirm it after deployment.

## Remaining Caveats

- Bitget historical fills imported during the worker outage do not contain a reliable realized-P&L field in the observed payload, so they cannot safely be used for reconstructed profit/loss.
- Strategy records with `status = submitted` mean the order request was accepted by the exchange API; a separate fill confirmation may still be needed for strict execution accounting.
- Unsupported `MSFTUSDT` remained in one saved symbol list and produces blocked cycles; supported symbols are AAPLUSDT and TSLAUSDT.
- No commit or GitHub push was made in this session.
