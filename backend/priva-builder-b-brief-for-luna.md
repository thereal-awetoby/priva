# Priva — Builder B (Backend/Agent) Brief for Luna

**Context for Luna:** You're helping Kayode (Builder B) build the backend/agent half of **Priva**, an entry for the Bitget AI Base Camp S2 hackathon (Agentic Trading track, deadline 9/21). Builder A is handling frontend. This doc is your reference — use it to help scaffold code, debug, and keep the build on schedule.

---

## 1. What Priva Is

Priva is an autonomous AI trading agent for tokenized U.S. stocks. It trades both spot and leveraged perpetual futures, but unlike most agent demos, it keeps its strategy and decision logic **private** — trades are submitted as encrypted intents so no one can watch, copy, or front-run it. The agent never holds the user's full private key or withdrawal rights; it operates under strict, hard-coded risk limits and runs 24/7 in the cloud. Users control it through a simple website (Autonomous Mode vs. Strategy Mode, with pre-built, Bitget Playbook, or user-defined custom strategies).

## 2. Builder B's Stack

- **Backend:** Python + FastAPI, hosted on Render free tier (+ keep-alive pinger)
- **Database:** Supabase (Postgres) — users, positions, activity log, strategies, settings
- **LLM:** Groq free tier — parses natural-language custom strategies, writes trade narration
- **Bitget:** Agent Hub + MCP, Agentic Account, `--paper-trading` mode (zero real funds needed)
- Everything is free-tier — no cost to build or demo

### Current authentication and account-connection state

The backend supports Supabase bearer-token verification and an encrypted
per-user runtime vault for Bitget demo credentials. Authenticated users can
connect, verify, inspect, and disconnect their own Bitget account through:

- `GET /auth/session`
- `POST /connection/bitget`
- `GET /debug/bitget-account`
- `POST /connection/bitget/disconnect`
- `POST /paper-trade`
- `GET /user/agent-loop`
- `GET /user/agent-settings`
- `POST /user/agent-settings`

The backend reads `SUPABASE_URL`, `SUPABASE_ANON_KEY`,
`PRIVA_AUTH_REQUIRED`, and `PRIVA_CREDENTIAL_ENCRYPTION_KEY`. The frontend
must send the Supabase access token as `Authorization: Bearer ...` and must
never persist Bitget secrets.

Authenticated users now receive separate runtime workers, Bitget clients, risk
engines, persisted strategy/risk/exit settings, and user-filtered cycle logs.
Credentials require the multi-user migration and service-role configuration to
restore after restart. The frontend still needs to adopt the authenticated
user-scoped endpoints before multi-user dashboard isolation is production-ready.

The multi-user Supabase migration is in `backend/supabase_multi_user.sql` and
must be run before enabling durable credential restoration. It adds encrypted
credential storage, user agent settings, and `user_id` filtering for
`agent_cycles`.

## 3. Builder B's System, End to End

```
Market Data Service → Strategy Engine → Risk Engine
        (price/volume,     (pre-built,      (max size, max
         OI, funding,       playbook,        daily loss, max
         liquidations)      custom A+B,      leverage, kill
                            backtests)       switch)
                     │
                     ▼
            Autonomous Loop (scheduler/worker)
            — runs constantly: pull data → decide → risk-check
                     │
                     ▼
            Encrypted Intent Generator  ← Priva's core privacy pitch
                     │
                     ▼
            Bitget Agentic Account (Agent Hub + MCP, no withdrawals)
                     │
                     ▼
            Trade Execution (spot/perps, paper mode)
                     │
                     ▼
            Supabase (Postgres) — logs everything
```

Reference repos worth mining for patterns (not copying wholesale):
- **NightDesk** (github.com/Pratiikpy/NightDesk) — risk gate/hard-rule firewall pattern, intent evaluation, paper-trading + evidence logging
- **Nocturne** (github.com/theeagle2407/Nocturne) — simple real Bitget public market data fetching, lightweight backtesting, dashboard patterns

## 3.1 Practical lessons from the reference repos

Use these as implementation guidance for Priva, not as a requirement to clone the entire repo architecture.

### From NightDesk: safety-first agent design
- Build a clear `evaluate_intent` / gate pattern before execution: the agent proposes a trade, then a deterministic risk/firewall layer decides whether it is allowed, capped, or rejected.
- Keep a replayable evidence trail: every decision, risk result, and trade should be logged with enough detail to explain why a trade was or was not allowed.
- Separate “research signal” from “execution proof.” The signal can be LLM-assisted or heuristic, but the execution layer should be deterministic and auditable.
- Be explicit about what is proven vs. what is still aspirational. Priva should avoid claiming a profitable edge unless the numbers are genuinely verified.
- Favor read-only verification first. If Bitget APIs are read-only or partially restricted, test the round-trip path before enabling write capability.

### From Nocturne: honest market-data and risk framing
- Use real market data and clearly document its provenance, especially Bitget public candle limits and where the data snapshot is truncated.
- Show the actual risk story, not just a shiny backtest: overnight and closed-market exposure matter for tokenized stocks when the underlying exchange is closed.
- Keep the methodology and results aligned. If the dashboard says “in-sample” or “out-of-sample,” the calculations should reflect that split cleanly.
- Present risk outputs as action plans, not just metrics. For Priva, the useful result is not only an indicator but a concrete response: HOLD, TRIM, FLATTEN, or reject.
- Build for reproducibility. The app should be able to regenerate the same metrics and boards from the same underlying data source.

### What this means for Priva's Playbook integration
- The current backend does not yet have a real Bitget Playbook connector. The current `/strategies` payload only labels one strategy as `type: "playbook"`; it is not yet a real Playbook-backed strategy source.
- The right approach is to normalize Playbook entries into the same strategy object shape used elsewhere in Priva (`id`, `name`, `type`, `description`, `status`, and a structured strategy payload or metadata block).
- Builder A should consume the backend `/strategies` response rather than hardcoding strategy data in the UI.
- Builder B should keep the strategy catalog honest: if a strategy comes from Playbook, the API should say so explicitly and return the exact configuration the backend can backtest or activate.
- Integration order for the reference repos should be: `NightDesk` first for firewall / intent evaluation, then `Nocturne` for transparent market-data and overnight risk framing, and only after that a real Playbook-backed strategy contract.

### NightDesk integration: what to implement now
- Add a deterministic `evaluate_intent` / risk-firewall step before any execution path is allowed.
- Return a clear verdict such as `ALLOW`, `ALLOW_CAPPED`, or `REJECT`.
- Log every intent, risk decision, and trade result so the app can explain exactly why a trade was or was not allowed.
- Keep the signal layer and execution proof layer separate; LLM-assisted reasoning can inform the signal, but execution must remain deterministic and auditable.

### Nocturne integration: what to implement next
- Surface real market-data provenance and clearly document where public data is truncated or limited.
- Show overnight / closed-market exposure and action plans like `HOLD`, `TRIM`, `FLATTEN`, or `REJECT`.
- Keep methodology and metrics aligned so in-sample / out-of-sample reasoning is honest and reproducible.
- Treat the dashboard as a risk and action layer, not only as a return visualization.

### Playbook integration: do this last, and only once the schema is real
- Do not expose Playbook as a live strategy source until Builder B defines a normalized payload the backend can actually backtest or activate.
- Only after that should Playbook be added to the `/strategies` catalog as a fully supported strategy type.
- Until then, the public strategy catalog should remain honest and limited to the two implemented built-ins plus any verified custom strategies.

## 3.1.1 Concrete Builder B backlog from the reference repos

Use the reference repos as a backlog source for what to build next; do not treat them as a clone requirement.

### Backlog items to implement first
- Build a deterministic `evaluate_intent` / risk-firewall layer that receives an intent, runs the hard rules, and returns `ALLOW`, `ALLOW_CAPPED`, or `REJECT`.
- Make every decision, risk result, and trade replayable via structured logs so the app can show: what the agent saw, what the rule engine decided, and what ran or was blocked.
- Separate the `signal` layer from the `execution proof` layer. Signals can use LLM-assisted reasoning or heuristics, but execution must be deterministic and auditable.
- Keep `Playbook` entries out of the public catalog until they are a real normalized strategy object that the backend can backtest or activate.
- Add an overnight-risk / closed-market view that explicitly shows exposure, gaps, and recommended actions such as `HOLD`, `TRIM`, or `FLATTEN`.
- Ensure the `/strategies` response is always the single source of truth for Builder A, including built-ins, custom strategies, and any future Playbook entries.

### Current repo state to preserve
- `momentum_breakout`, `mean_reversion`, and `overnight_gap` are the built-in strategies currently implemented in the backend and should remain the canonical built-ins.
- The backend already supports `/strategies`, `/strategies/{strategy_id}/activate`, `/strategies/{strategy_id}/backtest`, and `/strategies/parse`.
- Builder A's Strategy Lab panel has already been updated to consume `/strategies` and activate the selected strategy by ID, so the frontend should not reintroduce hardcoded strategy lists.

## 3.2 Strategy definitions for Builder B

These are the only built-in strategies currently implemented in Priva's backend. Keep these definitions stable and make the `/strategies` API reflect them exactly.

### 1) `momentum_breakout`
- Purpose: trend-following / continuation strategy.
- Trigger: compare the current `last_price` with the candle's `open_price`.
- Decision rule:
  - if `last_price > open_price`: emit `buy`
  - if `last_price < open_price`: emit `sell`
  - if roughly equal: emit `hold`
- Signal strength: normalized distance between the current price and the open price, capped to `1.0`.
- Meaning: the system is betting that an upward or downward move from the open will continue.
- Current backend behavior: the strategy returns `size = 1.0` for active signals and `size = 0.0` for `hold`.

### 2) `mean_reversion`
- Purpose: fade-the-move / reversal strategy.
- Trigger: compare the current `last_price` with the candle's `open_price` and compute deviation `((last_price - open_price) / open_price)`.
- Decision rule:
  - if deviation `>= 1%`: emit `sell`
  - if deviation `<= -1%`: emit `buy`
  - if within the neutral band (`-1%` to `+1%`): emit `hold`
- Signal strength: the absolute deviation, capped to `1.0`.
- Meaning: the system assumes extended moves above or below the open are likely to revert back toward baseline.
- Current backend behavior: the strategy explicitly uses a 1% threshold and returns `size = 1.0` only when a trade is triggered.

### Strategy contract expectations
- Every built-in strategy must return the same decision shape consumed by the risk engine and execution layer:
  - `action`
  - `size`
  - `leverage`
  - `reason`
  - `signal_strength`
- `/strategies` should expose the strategy catalog in a consistent format:
  - `id`
  - `name`
  - `type`
  - `status`
  - `description`
- `/strategies/{strategy_id}/activate` should activate a strategy by ID.
- `/strategies/{strategy_id}/backtest` should run a backtest on that strategy ID using candles.
- `/strategies/parse` should support either:
  - natural-language text (`text`) or
  - a structured strategy object (`strategy`)
- The currently verified structured payload shape in the backend is limited to:
  - `strategy.action` (`buy` or `sell`)
  - `strategy.comparison` (`open` or `close`)
  - `strategy.threshold_pct` (numeric percentage)
- Any broader form field list such as `entry_condition`, `exit_condition`, and similar placeholders are not yet verified backend contracts and should not be treated as final until Builder B confirms them.

### Important note on Playbook
- `playbook` is not a new strategy implementation yet. Right now it is only a label in the strategy list.
- For Builder B, the clean rule is: only define a Playbook-backed strategy once the backend has a real normalized payload for it.
- Until then, the real implemented strategies are exactly the two above, and the API should represent them honestly.

## 4. Non-Negotiables (never cut these if behind schedule)

1. The risk engine
2. The kill switch
3. The paper trading log (must run continuously from early on — judges require it, recommended ≥2 weeks)

If cutting scope: drop Bitget Playbook integration first, then drop one of the two custom-strategy input methods (keep either natural language or the structured form, not both), then polish/animations — in that order.

## 5. Day-by-Day Task List (Builder B only)

**Week 1 — Skeleton alive and thinking**
- **Day 1:** Start the FastAPI app. Every endpoint from the shared list (status, positions, PnL, risk usage, activity log, strategies, kill switch) returns mock data for now. Deploy to Render so it's live.
- **Day 2:** Connect to Bitget's public market data feed for tokenized US stocks. Log real prices to confirm it works.
- **Day 3:** Build the first version of the agent loop — pull market data, print a fake "decision," log it. Just needs to run on a timer, doesn't need to be smart yet.
- **Day 4:** Make the agent loop place real paper trades (Bitget paper environment). Confirm a trade is visible somewhere.
- **Day 5:** Build the Risk Engine — max position size, max daily loss, max leverage. Every trade must pass these checks before it's allowed. This is the safety net judges care about most.

**Week 2 — Dashboard and privacy**
- **Day 6:** Build the Intent Generator — turn agent decisions into structured "intents," simulate encrypting them before "submission." This is Priva's core privacy pitch — take time here.
- **Day 7:** Save every intent, trade, and risk check to Supabase. Turn on real `/positions` and `/activity-log` endpoints (swap out mock data).
- **Day 8:** Finish `/pnl` and `/risk-usage` endpoints so the dashboard has real numbers.
- **Day 9:** Wire the Kill Switch so it actually pauses the loop, not just flips a UI toggle.
  - ✅ Checkpoint: by end of Day 9, the dashboard should show a real paper trade happening live. Test end-to-end with Builder A.

**Week 3 — Strategies (the "wow" features)**
- **Day 10:** Build 2 simple pre-built strategies and backtest them (≥60 days data, last 30 held out for testing). Build `/strategies` and `/strategies/{id}/activate` endpoints.
- **Day 11:** Hook up Bitget Playbook to also generate/backtest a strategy, feed into the same `/strategies` list.
  - *Implementation note:* this is still pending in the current codebase. The first step is to define the Playbook-backed strategy contract clearly, then normalize Playbook entries into the same payload shape the backend already uses for built-in strategies.
- **Day 12:** Let a user type a strategy in plain English (e.g. "buy when RSI is below 30"), have an LLM (Groq) turn it into rules, then backtest it.
- **Day 13:** Build the structured-form version: entry conditions, exit conditions, position size, max leverage, stop loss/take profit — same backtest step at the end.
  - ✅ Checkpoint: by end of Day 13, a user should be able to write a strategy in English OR fill a form, see a real backtest, and activate it. Test both paths.

### Remaining work for the Builder A / Builder B handoff
- Real Playbook API integration is not yet implemented in the backend; keep it out of the live catalog until there is a real normalized payload.
- The frontend strategy lab already consumes `/strategies`, so Builder A should continue using that endpoint as the source of truth instead of reintroducing hardcoded strategy data.
- `/strategies` should remain the single source of truth for Builder A, including built-ins, custom strategies, and any future Playbook entries.
- Builder B should decide whether a `playbook` strategy is represented as a template, a normalized strategy object, or a directly backtestable payload before exposing it in the catalog.
- Builder A and Builder B should confirm the exact request/response contract for `POST /strategies/parse`, `POST /strategies/{strategy_id}/activate`, and `POST /strategies/{strategy_id}/backtest` before final UI implementation.
- For `POST /strategies/parse`, the current verified structured payload is intentionally narrow and should be treated as the baseline contract until Builder B approves any expanded form schema.

**Week 4 — Finish and polish**
- **Day 14:** Build the endpoints behind Risk & Settings (max position size, max daily loss, max leverage, allowed stocks). Make sure changing a setting actually changes risk engine behavior.
- **Day 15:** Keep the paper trading log running continuously — required for submission, don't let it pause for long stretches from here on.
- **Day 16:** Pull final numbers: return, Sharpe ratio, max drawdown, win rate — needed for the submission form.
- **Day 17 (together with Builder A):** Record a 2–3 min demo (agent trading autonomously, an encrypted intent being created, switch to Strategy Mode, create a custom strategy live, hit the kill switch, explain the privacy model). Write the project description + LLM-usage field. Post the required X post (must include #BitgetHackathon + @Bitget_AI). Submit before 9/21.

## 6. Submission Requirements Recap (Agentic Trading track)

- Runnable demo + a complete event → decision → execution flow (simulated/paper trading acceptable)
- Paper trading log actually run during the competition period, recommended ≥2 weeks
- Compliant X post (required)
- Project description covers: thesis, target user, validation data/metrics, progress, deliverables, and (optional) your take on AI Trading
- Judging: 50% quantitative (Sharpe, drawdown, win rate) + 50% judge scoring (decision explainability, agent architecture quality, risk control effectiveness)

---

**How to use this with Luna:** paste this whole doc into a new chat with Luna, then ask it to help you with whichever day you're currently on — e.g. "I'm on Day 6, help me design the Intent Generator" — and it has the full context to work from without you re-explaining the project each time.
