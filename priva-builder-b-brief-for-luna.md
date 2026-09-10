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
- **Day 12:** Let a user type a strategy in plain English (e.g. "buy when RSI is below 30"), have an LLM (Groq) turn it into rules, then backtest it.
- **Day 13:** Build the structured-form version: entry conditions, exit conditions, position size, max leverage, stop loss/take profit — same backtest step at the end.
  - ✅ Checkpoint: by end of Day 13, a user should be able to write a strategy in English OR fill a form, see a real backtest, and activate it. Test both paths.

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
