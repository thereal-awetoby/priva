"use client";

import { useState } from "react";

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
  const log = mode === "autonomous" ? autonomousLog : strategyLog;

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