"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8001";

const autonomousLog = [
  { time: "14:02", text: "Encrypted intent submitted — NVDA long 2x" },
  { time: "14:02", text: "Trade filled at $121.84" },
  { time: "13:47", text: "Risk limit check passed" },
  { time: "11:30", text: "Strategy mode → Autonomous" },
];

const strategyLog = [
  { time: "13:15", text: "Encrypted intent submitted — TSLA short 1.5x" },
  { time: "12:40", text: "Quiet Momentum signal fired — AAPL long" },
  { time: "10:05", text: "Strategy activated — Quiet Momentum" },
  { time: "09:50", text: "Backtest refreshed — Quiet Momentum" },
];

export default function ControlCenterPanel() {
  const [mode, setMode] = useState<"autonomous" | "strategy">("autonomous");
  const [market, setMarket] = useState<"futures" | "spot">("futures");
  const [takeProfit, setTakeProfit] = useState("5");
  const [stopLoss, setStopLoss] = useState("2");
  const [closeOnViolation, setCloseOnViolation] = useState(true);
  const [savingMarket, setSavingMarket] = useState(false);
  const log = mode === "autonomous" ? autonomousLog : strategyLog;

  useEffect(() => {
    fetch(`${API_BASE}/agent-settings`)
      .then((response) => response.json() as Promise<{ market?: "futures" | "spot" }>)
      .then((payload) => {
        if (payload.market === "spot" || payload.market === "futures") {
          setMarket(payload.market);
        }
        if (payload.take_profit_pct != null) setTakeProfit(String(payload.take_profit_pct));
        if (payload.stop_loss_pct != null) setStopLoss(String(payload.stop_loss_pct));
        if (payload.close_on_signal_violation != null) setCloseOnViolation(payload.close_on_signal_violation);
      })
      .catch(() => undefined);
  }, []);

  const updateMarket = async (nextMarket: "futures" | "spot") => {
    setMarket(nextMarket);
    setSavingMarket(true);
    try {
      const response = await fetch(`${API_BASE}/agent-settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          market: nextMarket,
          take_profit_pct: Number(takeProfit),
          stop_loss_pct: Number(stopLoss),
          close_on_signal_violation: closeOnViolation,
        }),
      });
      if (!response.ok) {
        throw new Error("Unable to update market");
      }
    } catch {
      setMarket(nextMarket === "futures" ? "spot" : "futures");
    } finally {
      setSavingMarket(false);
    }
  };

  return (
    <div>
      <div className="control-topline">
        <div className="status-pill">
          <span className="status-dot" />
          Running
        </div>
        <div className="app-actions" style={{ marginTop: 0 }}>
          <a className="btn" href="#">Pause</a>
          <a className="btn btn-danger" href="#">Kill switch</a>
        </div>
      </div>

      <div className="config-panel" style={{ marginBottom: 24 }}>
        <div className="config-head">
          <h3 className="config-title">Autonomous execution market</h3>
        </div>
        <p className="config-desc">Choose whether autonomous orders use Bitget spot or USDT futures.</p>
        <div className="mode-switch" aria-label="Autonomous execution market">
          <button className={market === "futures" ? "active" : ""} onClick={() => updateMarket("futures")} disabled={savingMarket}>
            Futures
          </button>
          <button className={market === "spot" ? "active" : ""} onClick={() => updateMarket("spot")} disabled={savingMarket}>
            Spot
          </button>
        </div>
        <div className="config-rows" style={{ marginTop: 16 }}>
          <label className="config-row">
            <span className="config-key">Take profit (%)</span>
            <input className="activity-search" type="number" min="0.1" step="0.1" value={takeProfit} onChange={(event) => setTakeProfit(event.target.value)} />
          </label>
          <label className="config-row">
            <span className="config-key">Stop loss (%)</span>
            <input className="activity-search" type="number" min="0.1" step="0.1" value={stopLoss} onChange={(event) => setStopLoss(event.target.value)} />
          </label>
          <label className="config-row">
            <span className="config-key">Close on opposite signal</span>
            <input type="checkbox" checked={closeOnViolation} onChange={(event) => setCloseOnViolation(event.target.checked)} />
          </label>
        </div>
        <button className="btn btn-primary" style={{ marginTop: 12 }} onClick={() => updateMarket(market)} disabled={savingMarket}>
          {savingMarket ? "Saving…" : "Save autonomous rules"}
        </button>
      </div>

      <div className="perf-row">
        <div className="perf-cell">
          <div className="perf-label">Total P&amp;L</div>
          <div className="perf-value up">+$18,240.12</div>
        </div>
        <div className="perf-cell">
          <div className="perf-label">Today&apos;s P&amp;L</div>
          <div className="perf-value up">+$412.30</div>
        </div>
        <div className="perf-cell">
          <div className="perf-label">Win rate</div>
          <div className="perf-value">61.4%</div>
        </div>
        <div className="perf-cell">
          <div className="perf-label">Max drawdown</div>
          <div className="perf-value down">−6.8%</div>
        </div>
      </div>

      <div className="risk-row">
        <div className="risk-label-row">
          <span>Risk usage</span>
          <span>42% of daily limit</span>
        </div>
        <div className="risk-bar">
          <div className="risk-bar-fill" style={{ width: "42%" }} />
        </div>
      </div>

      <div className="positions-section">
        <div className="panel-title">Positions</div>
        <table className="positions">
          <thead>
            <tr>
              <th>Asset</th>
              <th>Side</th>
              <th>Size</th>
              <th>P&amp;L</th>
              <th>Type</th>
              <th>Mode</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>NVDA</td>
              <td><span className="side-tag up">Long 2x</span></td>
              <td>$4,200.00</td>
              <td className="up">+$182.40</td>
              <td>Perp</td>
              <td><span className="mode-tag autonomous">Autonomous</span></td>
            </tr>
            <tr>
              <td>TSLA</td>
              <td><span className="side-tag down">Short 1.5x</span></td>
              <td>$2,800.00</td>
              <td className="down">−$64.10</td>
              <td>Perp</td>
              <td><span className="mode-tag strategy">Strategy</span></td>
            </tr>
            <tr>
              <td>AAPL</td>
              <td><span className="side-tag up">Long</span></td>
              <td>$1,500.00</td>
              <td className="up">+$22.05</td>
              <td>Spot</td>
              <td><span className="mode-tag strategy">Strategy</span></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="mode-activity-block">
        <div className="control-mode-center">
          <div className="mode-switch">
            <button
              className={mode === "autonomous" ? "active" : ""}
              onClick={() => setMode("autonomous")}
            >
              Autonomous
            </button>
            <button
              className={mode === "strategy" ? "active" : ""}
              onClick={() => setMode("strategy")}
            >
              Strategy
            </button>
          </div>
        </div>

        <div className="panel-title panel-title-center">
          Recent activity — <span>{mode === "autonomous" ? "Autonomous" : "Strategy"}</span>
        </div>
        <div className="activity-log">
          {log.map((row, i) => (
            <div className="log-row" key={i}>
              <span className="log-time">{row.time}</span>
              <span>{row.text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}