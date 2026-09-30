# Priva

**A bounded agent that trades tokenized U.S. stocks on Bitget paper — and does not publish the rule.**

Spot and perpetual futures. Five-minute loop. Hard risk gates. The book stays inside the process. What leaves is a SHA-256 intent hash, not the strategy.

This is **not** FHE, **not** a TEE, and **not** a dark pool. Bitget still sees the fill.

[Live desk](https://priva-rho.vercel.app) · [API health](https://priva-499h.onrender.com/health) · [Repo](https://github.com/thereal-awetoby/priva)

Bitget AI Base Camp S2 · **Agentic Trading** · **Open Theme** · paper only (`paptrading: 1`)

---

## Overview

Open the [desk](https://priva-rho.vercel.app). Sign in. The running process is a **worker**, not a chat box.

| | |
|---|---|
| Decision-maker | Gemini chooses hold, buy, or sell each cycle (`backend/app/agent_loop.py`). Risk can still refuse. |
| Cycle | Read → Model decides → Risk → Hash → Send. Any gate fails → nothing is sent |
| Demo | https://priva-rho.vercel.app |
| Paper log | [`priva-activity-csv-2026-09-30.csv`](./priva-activity-csv-2026-09-30.csv) (raw) · [`priva_completed_trades.csv`](./priva_completed_trades.csv) (32 scored closes) |
| Risk | `$25k` position · `$1.5k` daily loss · `5x` · AAPL/TSLA allow-list · trade-only keys · kill switch |
| Privacy | Hash of the intent. Fill still visible to the venue |

**One cycle (the Agentic unit).** Every five minutes the worker:

1. **Read** live Bitget marks for AAPL / TSLA
2. **Model decides** — Gemini returns hold, buy, or sell. The built-in book is a hint only
3. **Risk** — size, daily loss, leverage, allow-list
4. **Hash** — SHA-256 fingerprint of the intent
5. **Send or refuse** — Bitget paper (`paptrading: 1`). If Gemini is down, the cycle holds. If risk fails, nothing is sent. The row is still logged.

Hold is not a no-op. On hold, the worker still checks open spot and futures against take-profit and stop-loss.

Example row from the raw tape (pre-change veto era):

`2026-09-29T12:45:08` · `TSLAUSDT` · sell · autonomous · **blocked** · `gemini veto`

New cycles log `decision.source = model` instead of a veto gate.

Observed paper tape (AAPL/TSLA only): equity ~$19,855 · desk PnL **−$116** · **32** logged closes · **23** with a PnL figure summing to **−$125.73**. Short window. No Sharpe.

---

## For users

Priva only talks to **Bitget Demo Trading**. Live keys will not work. The worker can place paper orders. It cannot withdraw.

### 1. Open Bitget Demo

1. Sign in at [bitget.com](https://www.bitget.com).
2. Top nav → **Futures**.
3. In the menu, open **Demo trading** (demo trading with zero funding risk).
4. Confirm the header shows the green **Demo** badge. If it says Live, you are in the wrong venue.

<img width="1080" height="1080" alt="Open Bitget Demo trading" src="https://github.com/user-attachments/assets/717b0d50-b8ea-495e-bc1a-fe04dc437d5d" />

### 2. Create a **demo** API key

Do this **inside Demo**, not on the live API-keys page.

1. Top-right profile → **API management**.
2. You should land on a page that says **Create new demo trade API key** (not a live key).
3. Create one key. Set a passphrase. Save:

   - API key
   - API secret
   - Passphrase

4. Permissions: **trade only**. No withdrawals. No transfers.

If the button says anything other than demo / paper, stop. That key must never be pasted into Priva.

<img width="1080" height="1080" alt="Create a Bitget demo API key" src="https://github.com/user-attachments/assets/39b1b9c0-bd26-4877-b69e-f53ec34a12f5" />

### 3. Fund the paper account (optional)

Demo starts with paper USD / USDT. You can top it up:

1. In the demo terminal, open the briefcase / **Assets**.
2. Open **Adjust demo trading funds**.
3. Add USDT (and USD if you want the spot side funded).

A ~$20,000 paper balance is enough to match the desk you see in the demo.

<img width="1080" height="1080" alt="Adjust Bitget demo trading funds" src="https://github.com/user-attachments/assets/5ea8902b-e360-4a70-9a15-565d3c1a461a" />

### 4. Open Priva and connect

1. Go to [priva-rho.vercel.app](https://priva-rho.vercel.app).
2. **Create an account** (email + password) or sign in.
3. Open the **Confirm your email address** mail from Supabase Auth. Click **Confirm email address**. Until that link is used, sign-in stays blocked.
4. You land on **Connect your Bitget demo account**.
5. Paste API key, API secret, passphrase.
6. Save. The desk stays locked until the paper key verifies.

Priva stores those credentials encrypted in a vault. The worker never holds your full exchange private key. Withdrawal permission is never requested.

<img width="1080" height="1080" alt="Priva sign in and confirm email" src="https://github.com/user-attachments/assets/bf776c90-4c19-43a2-8af8-1de59f738f11" />
<img width="1050" height="788" alt="Connect Bitget demo account in Priva" src="https://github.com/user-attachments/assets/b7680658-1831-412b-b384-adf1b382000d" />

### 5. Run the desk

| Screen | What to do |
|---|---|
| Control Center | Confirm **Worker running**, **Paper trading only**. Watch spot + futures equity. |
| Risk & access | Set caps first. Defaults: `$25,000` position · `$1,500` daily loss · `5x` · AAPL + TSLA only. |
| Strategy Lab | Leave **Autonomous**, or activate a built-in book, or write English / JSON and activate. The book is a hint. Gemini still chooses the send. Risk still gates. |
| Activity | This is the tape. Turn on **Show holds & evaluations**. Export CSV when you want a replay. |

Kill switch is one control: it stops the worker and can flash-close open futures.

### 6. Read one row

A useful Activity row has: time, mode (autonomous / strategy), symbol, model decision, risk ALLOW or BLOCK, intent hash, sent or not sent.

`symbol not available on this market` is a mapping miss, not a risk block. Filter those out when you read the tape. Logical names on the desk are `AAPLUSDT` / `TSLAUSDT`. Bitget spot tokens are `RAAPLUSDT` / `RTSLAUSDT`.

### What Priva will not do

- Use a live Bitget key
- Withdraw or transfer
- Hide the fill from Bitget
- Trade names outside the allow-list
- Run the loop if the demo key fails verification

---

## Thesis

Public agents leak the book. Chat agents wait for a prompt. Over-permissioned keys can withdraw.

Priva’s bet: an unattended agent is only safe if those three are fixed in one product.

1. **Scheduled.** A cycle every five minutes. Not a prompt.
2. **Gated.** Size, daily loss, leverage, allow-list — checked before every send.
3. **Quiet.** Strategy code never leaves the process. Activity stores a fingerprint of the decision. Change the logged intent and the hash no longer matches.

Gemini chooses hold, buy, or sell. The risk engine can still refuse. If Gemini is down, the cycle holds.

Autonomy without a wall is only faster risk. Privacy that pretends the exchange cannot see the order is a lie. Priva does neither.

```
  marks (AAPL / TSLA)
        |
        v
  +---------+   hold     +----------+
  |  Model  |----------->| not sent |--> log + wait
  +----+----+            +----------+
       | buy / sell
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

---

## Product

**Desk** — [priva-rho.vercel.app](https://priva-rho.vercel.app)

| Screen | What you should notice |
|---|---|
| Control Center | Worker running, next cycle, spot + futures equity, kill switch, Autonomous / Strategy |
| Strategy Lab | Four built-in books + custom English or JSON. Activate. Same risk spine. Book is a hint to the model. |
| Risk & access | Caps are not suggestions. Trade only. No withdrawals. No transfers. |
| Activity | Mode-separated tape. Intent hash on sends. CSV export is the replay. |

**Modes**

- **Autonomous** — built-in books as hints (momentum breakout, mean reversion, overnight gap, AAPL/TSLA pairs). Gemini chooses the action.
- **Strategy** — the book the user activated is still a hint. The model does not get a side door around risk.

**Default caps**

`$25,000` max position · `$1,500` max daily loss · `5x` max leverage · allow-list **AAPL + TSLA only**.

---

## Privacy

| Stays inside the agent | What leaves |
|---|---|
| Strategy code / JSON book | Normal Bitget paper order |
| Decision logic | Fill, qty, price — visible to the venue |
| Full user private key | Short intent hash in Activity |

The landing line is: the agent trades on its own; the rule set stays inside; the ledger shows a hash, not the book that produced it.

Credentials sit in a Fernet vault (`PRIVA_CREDENTIAL_ENCRYPTION_KEY`). The worker never holds the user’s full exchange private key.

---

## Paper numbers

Observed on the running demo account. Not a backtest. Not out-of-sample.

| | Observed |
|---|---|
| Paper equity | ~$19,855 |
| Desk realized PnL | **−$116** |
| Scored closes | 32 open→close pairs |
| Closes with a PnL figure | 23 |
| Sum of those 23 | **−$125.73** |
| Win rate | ~48.5% |
| Max drawdown | ~−0.65% |
| Universe | AAPLUSDT, TSLAUSDT |
| Live funds | none |

Some early demo TSLA / AAPL names rejected (`symbol not available`, `Parameter … does not exist`). Those are old mapping misses, not risk blocks. Holds mean the cycle ran and chose not to send. There is no Sharpe on this window.

Paper log:

- [`priva-activity-csv-2026-09-30.csv`](./priva-activity-csv-2026-09-30.csv) — raw export
- [`priva_completed_trades.csv`](./priva_completed_trades.csv) — 32 scored closes

---

## Architecture

```
priva-web  (Next.js, Vercel)
    |
    |  Bearer <Supabase access token>
    v
backend   (FastAPI, Render)
    |-- agent_loop.py        5-minute worker + Gemini decide
    |-- strategy.py          books + English/JSON parse (hints)
    |-- risk_engine.py       caps, allow-list, kill
    |-- paper_execution.py   Bitget paper client
    |-- user_runtime.py      per-user worker
    |-- auth.py              Supabase
    v
Bitget demo  +  Supabase (auth, cycle log, encrypted keys)
```

| Path | Role |
|---|---|
| `backend/app/agent_loop.py` | Cycle + model decision |
| `backend/app/risk_engine.py` | Wall |
| `backend/app/paper_execution.py` | Paper send |
| `backend/app/strategy.py` | Books + parse + activate |
| `backend/app/symbols.py` | `AAPLUSDT` → `RAAPLUSDT`, `TSLAUSDT` → `RTSLAUSDT` |
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

## Quick start (builders)

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
| `GEMINI_API_KEY` | Model decision. Missing key → hold |

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
- Hidden orders on Bitget
- A 60-day out-of-sample Sharpe

---

## License

Hackathon submission. Ask before you reuse the name or the desk.
