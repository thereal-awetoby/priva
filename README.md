# Priva

**A bounded agent that trades tokenized U.S. stocks on Bitget paper — and does not publish the rule.**

Spot and perpetual futures. Five-minute loop. Hard risk gates. The book stays inside the process. What leaves is a SHA-256 intent hash, not the strategy.

This is **not** FHE, **not** a TEE, and **not** a dark pool. Bitget still sees the fill.

[Live desk](https://priva-rho.vercel.app) · [API health](https://priva-499h.onrender.com/health) · [Repo](https://github.com/thereal-awetoby/priva)

Bitget AI Base Camp S2 · **Agentic Trading** · **Open Theme** · paper only (`paptrading: 1`)

---

## For judges (90 seconds)

Open the [desk](https://priva-rho.vercel.app). Sign in. You should see a **worker**, not a chat box.

| Handbook ask | Where it lives |
|---|---|
| Agent is the decision-maker | `backend/app/agent_loop.py` — 5-minute cycle, no human in the loop |
| Event → decision → execution | Read → Decide → Risk → Hash → Send. Any gate fails → nothing is sent |
| Runnable demo | https://priva-rho.vercel.app |
| Paper log | Activity panel + CSV export. Mode + intent hash on each row |
| Risk control | `$25k` position · `$1.5k` daily loss · `5x` · AAPL/TSLA allow-list · trade-only keys · kill switch |
| Honest privacy | Hash of the intent. Fill still visible to the venue |

Observed paper tape used in the demo (AAPL/TSLA only): equity ~$19,855 · PnL **−$116** · win rate ~48.5% · max DD ~−0.65%. Short window. No Sharpe. We would rather show a small honest loss than a backtest with no agent attached.

Then read **Thesis**. Skip `priva-web/README.md` — leftover create-next-app boilerplate. Skip `SESSION_HANDOFF*` and `BUILDER_A_HANDOFF.md` — internal notes, not the spec.

---

## Thesis

Public agents leak the book. Chat agents wait for a prompt. Over-permissioned keys can withdraw.

Priva’s bet: an unattended agent is only safe if those three are fixed in one product.

1. **Scheduled.** A cycle every five minutes. Not a prompt.
2. **Gated.** Size, daily loss, leverage, allow-list — checked before every send.
3. **Quiet.** Strategy code never leaves the process. Activity stores a fingerprint of the decision. Change the logged intent and the hash no longer matches.

Autonomy without a wall is only faster risk. Privacy that pretends the exchange cannot see the order is a lie. Priva does neither.

```
  marks (AAPL / TSLA)
        |
        v
  +---------+   fail     +----------+
  |  Decide |----------->| not sent |--> log + wait
  +----+----+            +----------+
       | pass
       v
  +---------+   fail
  |  Risk   |-----------> not sent
  +----+----+
       | pass
       v
  +---------+
  |  Hash   |  SHA-256 of the intent
  +----+----+
       v
  +---------+
  |  Send   |  Bitget paper, paptrading: 1
  +---------+
```

Hold is not a no-op. On a hold cycle the worker still checks open spot and futures against take-profit and stop-loss.

---

## Who it is for

Self-directed Bitget retail who already touch tokenized U.S. stocks, will start on paper, and will not give a bot withdraw permission.

Not “all traders.”

| | |
|---|---|
| Risk appetite | Conservative to moderate. Paper first. |
| Capital | Demo desk ~$20k notional. Live target after paper: `$5k–$25k` (matches the default cap). |
| Frequency | One cycle / five minutes. Not HFT. Not click-trading. |
| Market | Bitget tokenized U.S. stocks, spot + perps, `AAPLUSDT` / `TSLAUSDT` |
| Job to be done | Connect a paper key, set the wall, pick Autonomous or a named book, leave. Export the tape. |

What this segment still lacks elsewhere: a scheduled agent, a hard wall in front of every send, and a privacy sentence that does not overclaim.

---

## Product

**Desk** — [priva-rho.vercel.app](https://priva-rho.vercel.app)

| Screen | What you should notice |
|---|---|
| Control Center | Worker running, next cycle, spot + futures equity, kill switch, Autonomous / Strategy |
| Strategy Lab | Four built-in books + custom English or JSON. Activate. Same risk spine. |
| Risk & access | Caps are not suggestions. Trade only. No withdrawals. No transfers. |
| Activity | Mode-separated tape. Intent hash on sends. CSV export is the replay. |

**Modes**

- **Autonomous** — built-in books (momentum breakout, mean reversion, overnight gap, AAPL/TSLA pairs).
- **Strategy** — the book the user activated. The model does not get a side door around risk.

**Default caps**

`$25,000` max position · `$1,500` max daily loss · `5x` max leverage · allow-list **AAPL + TSLA only**.

---

## Privacy

| Stays inside the agent | What leaves |
|---|---|
| Strategy code / JSON book | Normal Bitget paper order |
| Decision logic | Fill, qty, price — visible to the venue |
| Full user private key | Short intent hash in Activity |

Credentials sit in a Fernet vault (`PRIVA_CREDENTIAL_ENCRYPTION_KEY`). The worker never holds the user’s full exchange private key.

---

## Paper numbers

Observed on the running demo account. Not a backtest. Not out-of-sample.

| | Observed |
|---|---|
| Paper equity | ~$19,855 |
| Realized PnL | **−$116** |
| Win rate | ~48.5% |
| Max drawdown | ~−0.65% |
| Universe | AAPLUSDT, TSLAUSDT |
| Live funds | none |

Some demo TSLA names rejected. There is no Sharpe on this window because the window does not deserve one.

Agentic track artifact is the **competition paper log**, not a 60-day OOS report. That log is Activity → Export CSV.

---

## Architecture

```
priva-web  (Next.js, Vercel)
    |
    |  Bearer <Supabase access token>
    v
backend   (FastAPI, Render)
    |-- agent_loop.py        5-minute worker
    |-- strategy.py          books + English/JSON parse
    |-- risk_engine.py       caps, allow-list, kill
    |-- paper_execution.py   Bitget paper client
    |-- auth.py              Supabase
    v
Bitget demo  +  Supabase (auth, cycle log, encrypted keys)
```

| Path | Role |
|---|---|
| `backend/app/agent_loop.py` | Cycle |
| `backend/app/risk_engine.py` | Wall |
| `backend/app/paper_execution.py` | Paper send |
| `backend/app/strategy.py` | Books + parse + activate |
| `backend/app/auth.py` | Session |
| `priva-web/` | Desk UI |

---

## Stack

- Desk: Next.js (`priva-web`) on Vercel
- Worker: FastAPI + Uvicorn (`backend`) on Render
- Auth, logs, encrypted keys: Supabase
- Venue: Bitget demo, hedge mode, `paptrading: 1`
- Period: 5 minutes
- Universe: `AAPLUSDT`, `TSLAUSDT` (`MSFTUSDT` blocked)

---

## Quick start

### Worker

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Health: http://127.0.0.1:8001/health

```bash
cd backend && python -m pytest -q
```

### Desk

```bash
cd priva-web
npm install
npm run dev
```

http://localhost:3000 — point the desk at the local API.

Production desk already uses `https://priva-499h.onrender.com`.

---

## Environment

### `backend`

| Variable | Point |
|---|---|
| `AGENT_WATCHED_SYMBOLS` | `AAPLUSDT,TSLAUSDT` |
| `SUPABASE_URL` | Project URL |
| `SUPABASE_ANON_KEY` | Anon |
| `SUPABASE_SERVICE_ROLE_KEY` | Server only — never ship to the browser |
| `PRIVA_CREDENTIAL_ENCRYPTION_KEY` | Fernet, 44 chars |

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### `priva-web`

Public env only: API base (`https://priva-499h.onrender.com` in prod) and Supabase URL + anon key. Same project as the worker.

Never put the service role key or Bitget secrets in `NEXT_PUBLIC_*`.
Bitget API credentials are entered per user in the authenticated app and stored
encrypted in Supabase; do not configure shared Bitget credentials in Render.

---

## API

Open:

- `GET /health`
- `GET /status`

Bearer (`Authorization: Bearer <Supabase access token>`):

```
GET  /strategies
POST /strategies/parse
POST /strategies/{id}/activate
GET  /risk-settings
POST /risk-settings
POST /risk-check
POST /paper-trade
GET  /account/balance
GET  /account/balance-history
GET  /pnl
GET  /activity-log
GET  /user/agent-loop
POST /user/agent-settings
POST /kill-switch
```

---

## What this repo is not

- Live funds
- Withdrawals or transfers
- A universe past AAPL and TSLA
- A claim that Bitget cannot see the order
- A 60-day out-of-sample Sharpe

If the paper worker keeps running through the deadline, the CSV gets longer. That is the only metric that should move.

---

## License

Hackathon submission. Ask before you reuse the name or the desk.
