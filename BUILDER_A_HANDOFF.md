# Builder A Handoff List

This is the current handoff for Builder A. The backend is already verified and live on Render, so Builder A should treat the backend as the source of truth for strategy, risk, and execution flows.

## 1. Live backend base URL

```text
https://priva-499h.onrender.com
```

## 2. What Builder A should use

Use these endpoints from Builder A:

- `GET /strategies` — fetch the available strategy catalog
- `POST /strategies/parse` — convert natural-language input into a structured strategy payload
- `GET /risk-settings` — fetch current risk settings
- `POST /risk-settings` — update allowed symbols and risk limits
- `POST /risk-check` — validate a proposed trade before submitting it
- `POST /paper-trade` — submit a trade to the Bitget paper environment
- `POST /strategies/{strategy_id}/backtest` — run a backtest and get metrics

## 3. Recommended Builder A flow

1. Load the strategy catalog with `GET /strategies`.
2. Send natural-language strategy text to `POST /strategies/parse`.
3. If the user wants provider-backed parsing, send `use_gemini: true`.
4. Use `GET /risk-settings` and `POST /risk-settings` to surface and update symbol/risk limits.
5. Run `POST /risk-check` before each proposed trade.
6. Submit execution with `POST /paper-trade`.
7. Run `POST /strategies/{strategy_id}/backtest` when metrics or strategy validation are needed.

## 4. Important Builder A rules

- Do not collect or store provider API keys in the browser.
- All provider-backed parsing is handled server-side by the backend.
- The backend currently supports `use_gemini`; older `use_qwen` and `use_grok` payloads are tolerated for compatibility but should not be used as the target path.
- Supported Bitget paper symbols are currently `AAPLUSDT` and `TSLAUSDT`.
- Partial closes are intentionally not supported.
- Builder A should not modify or rebuild the backend unless explicitly requested.

## 5. Verified backend state

The backend has already been verified for:

- `GET /health`
- `GET /strategies`
- `POST /strategies/parse`
- `GET /risk-settings`
- `POST /risk-settings`
- `POST /risk-check`
- `POST /paper-trade`
- `POST /strategies/{strategy_id}/backtest`
- `GET /pnl` (including `win_rate_pct` and `max_drawdown_pct`)
- `GET /activity-log` (including `mode` metadata)

## 5.1 Risk settings defaults and current logic

The backend risk engine currently starts with these hardcoded defaults in `RiskEngine.__init__()`:

- `max_position_size = 25000`
- `max_daily_loss = 1500`
- `max_leverage = 5.0`
- `enabled = True`
- `allowed_symbols = None` (unrestricted unless explicitly set)

The live enforcement logic in `evaluate_trade()` is:

- compute `notional = qty * entry_price`
- reject if the symbol is not in `allowed_symbols` when the allowlist is active
- reject if `notional > max_position_size`
- reject if `current_daily_pnl <= -max_daily_loss`
- reject if `leverage > max_leverage`
- reject if adding the proposed notional to any same-symbol existing position would exceed `max_position_size`

Builder A should treat `GET /risk-settings` and `POST /risk-settings` as the source of truth for current live settings and use them in the UI when exposing risk controls.

## 5.2 Strategy defaults and current logic

The backend currently exposes two built-in strategies:

### Momentum Breakout

- Trigger: compare `last_price` versus `open_price`
- Decision rules:
  - `buy` if `last_price > open_price`
  - `sell` if `last_price < open_price`
  - `hold` if approximately equal
- Default outputs:
  - `size = 1.0` when a trade is active
  - `size = 0.0` when `hold`
  - `leverage = 1.0`
  - `signal_strength` is normalized to a value in `[0, 1]`

### Mean Reversion

- Trigger: compare `last_price` to `open_price` and compute deviation `((last_price - open_price) / open_price)`
- Default threshold: `1%`
- Decision rules:
  - `sell` if deviation `>= 1%`
  - `buy` if deviation `<= -1%`
  - `hold` otherwise
- Default outputs:
  - `size = 1.0` when a trade is active
  - `size = 0.0` when `hold`
  - `leverage = 1.0`
  - `signal_strength` is the absolute normalized deviation, capped at `1.0`

The backend now also supports per-strategy configuration overrides for built-ins via the same strategy-config contract used by custom strategies, including:

- `position_size` / `size`
- `leverage`
- `take_profit_pct` / `take_profit`
- `stop_loss_pct` / `stop_loss`
- `threshold_pct`

These override values are accepted in the parse path and applied to the chosen builtin strategy before the strategy is returned or used in a backtest.

## 6. Current strategy and execution contract

### Strategy decision shape

```json
{
  "action": "buy",
  "size": 1.0,
  "leverage": 1.0,
  "reason": "...",
  "signal_strength": 0.5
}
```

### Parser output

The parser can return either a builtin strategy match or a structured strategy payload, and it performs strict validation before accepting input.

### Supported parse payloads

The backend currently supports both of these request modes:

1. Natural-language text:
   - `{"text": "..."}`
   - optional provider path: `{"text": "...", "use_gemini": true}`
2. Structured strategy payload:
   - `{"strategy": {"action": "buy|sell", "comparison": "open|close", "threshold_pct": 1.0}}`
   - additional supported config fields for built-ins include `position_size`, `size`, `leverage`, `take_profit_pct`, `take_profit`, `stop_loss_pct`, and `stop_loss`

### Metrics already implemented

Yes — the `win rate` and `max drawdown` work was added earlier and is live in the backend:

- `GET /pnl` now returns `win_rate_pct` and `max_drawdown_pct`
- `GET /activity-log` now includes `mode` metadata for each entry

## 7. Builder A checklist

- [ ] Wire `GET /strategies` into the strategy catalog view
- [ ] Wire `POST /strategies/parse` into the natural-language strategy UX
- [ ] Add `use_gemini: true` support on the Builder A request side
- [ ] Surface `GET /risk-settings` and `POST /risk-settings` in the settings UI
- [ ] Add a pre-trade `POST /risk-check` call before order submission
- [ ] Connect `POST /paper-trade` to the trading UI
- [ ] Display backtest results from `POST /strategies/{strategy_id}/backtest`
- [ ] Keep the backend untouched unless a backend change is explicitly requested

## 8. Known limitations to communicate to Builder A

- Realized PnL is scoped to the current backend session.
- The configured Bitget paper account supports only `AAPLUSDT` and `TSLAUSDT`.
- `MSFTUSDT` should not be used in the current paper environment.
- The backend handles provider secrets server-side; Builder A should not expose them.

## 9. Next step after this handoff

Once Builder A is integrated against the verified API contract, the next focus can be demo polish and presentation rather than backend development.
