# Priva

Bounded autonomous agent for tokenized U.S. stocks on Bitget paper.

Trades **spot and perpetual futures**. The rule set stays inside the agent. What leaves is a SHA-256 intent hash, not the book.

This is **not** FHE, **not** a TEE, and **not** a dark pool. The exchange still sees the fill.

**Hackathon:** Bitget AI Base Camp S2 · **Track:** Agentic Trading · **Sub-theme:** Open Theme

| | |
|---|---|
| Live desk | https://priva-rho.vercel.app |
| API | https://priva-499h.onrender.com |
| Source | https://github.com/thereal-awetoby/priva |

`GET https://priva-499h.onrender.com/health` should return ok if the worker is up.

---

## Why it exists

Public agents leak the book. Chat windows wait for a prompt. Over-permissioned API keys can withdraw.

Priva is a scheduled worker, not a chatbot:

1. Read live Bitget marks (AAPL, TSLA)
2. Decide — autonomous book, or the book the user activated
3. Risk — size, daily loss, leverage, allow-list
4. Hash the intent
5. Send a **paper** order (`paptrading: 1`), or send nothing

If any gate fails, nothing is sent. The cycle is logged. The next pass starts on schedule.

---

## What a user does

1. Open the desk and sign in
2. Connect a Bitget **demo** key (trade-only — no withdrawals)
3. Set caps: position, daily loss, leverage, allow-list
4. Leave **Autonomous** on, or switch to **Strategy** and activate a book (pre-built, English, or JSON)
5. Watch Control Center and Activity
6. Hit kill switch if the worker must stop

Default caps in the desk: **$25,000** position · **$1,500** daily loss · **5x** · **AAPL + TSLA only**.

---

## Repo layout

```
backend/          FastAPI worker, risk engine, Bitget paper client, agent loop
  app/agent_loop.py
  app/risk_engine.py
  app/paper_execution.py
  app/strategy.py
priva-web/        Next.js desk (Control Center, Strategy Lab, Risk, Activity)
```

Ignore `SESSION_HANDOFF*` and `BUILDER_A_HANDOFF.md`. Those are internal notes, not product docs.

---

## Privacy — honest version

| Stays inside the agent | What this is not |
|---|---|
| Strategy code / JSON book | A hidden fill |
| Decision logic | FHE / TEE / ZK |
| Full user private key | A dark pool |

Activity stores a short intent hash. Change the logged decision and the hash no longer matches. The Bitget order is still a normal paper API order.

Credentials sit in an encrypted vault (`PRIVA_CREDENTIAL_ENCRYPTION_KEY`). The process never holds the user's full exchange private key.

---

## Stack

- Desk: Next.js (`priva-web`), hosted on Vercel
- Worker: FastAPI + Uvicorn (`backend`), hosted on Render
- Auth + logs + encrypted keys: Supabase
- Venue: Bitget demo / paper, hedge mode, `AAPLUSDT` and `TSLAUSDT`
- Agent period: 5 minutes

---

## Quick start (local)

### Worker

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Health: http://127.0.0.1:8001/health

Tests:

```bash
cd backend
python -m pytest -q
```

### Desk

```bash
cd priva-web
npm install
npm run dev
```

Point the desk at the local API (see env below), then open http://localhost:3000.

Production desk already talks to `https://priva-499h.onrender.com`.

---

## Environment

### `backend`

| Variable | Point |
|---|---|
| `BITGET_API_KEY` / `BITGET_API_SECRET` / `BITGET_API_PASSPHRASE` | Paper keys only |
| `BITGET_POSITION_MODE` | `hedge` |
| `AGENT_WATCHED_SYMBOLS` | `AAPLUSDT,TSLAUSDT` |
| `SUPABASE_URL` | project URL |
| `SUPABASE_ANON_KEY` | anon |
| `SUPABASE_SERVICE_ROLE_KEY` | server only — never ship to the browser |
| `PRIVA_AUTH_REQUIRED` | `true` in production |
| `PRIVA_CREDENTIAL_ENCRYPTION_KEY` | Fernet key, 44 chars |

Generate the vault key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### `priva-web`

Typical Next public vars (name them to match whatever `priva-web` already reads):

| Variable | Point |
|---|---|
| Bitget-facing API base | `https://priva-499h.onrender.com` in prod |
| Supabase URL + anon key | same project as the worker |

Do not put the service role key or Bitget secrets in Vercel public env.

---

## Agent loop

Every five minutes, per user with a connected paper key:

```
Read → Decide → Risk → Hash → Send | Not sent
```

- **Autonomous** — built-in books (momentum breakout, mean reversion, overnight gap, AAPL/TSLA pairs). Hold cycles still evaluate take-profit / stop-loss on open spot and futures.
- **Strategy** — the active book only. Same risk spine. No second path around the gates.
- **Kill switch** — stops the worker and can flash-close open futures.

Paper orders go through Bitget (`paptrading: 1`). This is not a local simulator.

---

## Useful API

Unauthenticated:

- `GET /health`
- `GET /status`

Bearer token (Supabase access token) for user routes:

- `GET /strategies` · `POST /strategies/parse` · `POST /strategies/{id}/activate`
- `GET /risk-settings` · `POST /risk-settings` · `POST /risk-check`
- `POST /paper-trade`
- `GET /account/balance` · `GET /account/balance-history` · `GET /pnl` · `GET /activity-log`
- `GET /user/agent-loop` · `POST /user/agent-settings`
- `POST /kill-switch`

---

## Paper results (observed, not a backtest)

From the running paper desk used in the S2 demo (AAPL/TSLA only):

- Equity ≈ $19,855 paper
- Realized PnL ≈ **−$116**
- Win rate ≈ **48.5%**
- Max drawdown ≈ **−0.65%**

The tape is short. Some demo TSLA names rejected. We are not publishing a Sharpe on that window.

Agentic track artifact is the **paper log** (Activity CSV), not a 60-day out-of-sample backtest.

---

## What this repo is not

- Live funds
- Withdrawals or transfers
- Universe beyond AAPL / TSLA
- A claim that Bitget cannot see the order

---

## License

Personal hackathon submission. Ask before you reuse the name or the desk.
