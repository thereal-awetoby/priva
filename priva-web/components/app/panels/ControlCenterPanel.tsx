"use client";

import { useState, useEffect } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { timeAgo, cleanSymbol } from "@/lib/format";

type Position = Record<string, any>;
type ActivityEntry = Record<string, any>;
type EquityPoint = { timestamp?: string; created_at?: string; balance?: number; equity?: number };

function EquityCurve({ points }: { points: EquityPoint[] }) {
  const values = points.map((point) => Number(point.balance ?? point.equity ?? 0));
  const width = 720;
  const height = 170;
  const padding = 12;
  const min = values.length ? Math.min(...values) : 0;
  const max = values.length ? Math.max(...values) : 1;
  const range = max - min || 1;
  const path = values
    .map((value, index) => {
      const x = padding + (index / Math.max(values.length - 1, 1)) * (width - padding * 2);
      const y = height - padding - ((value - min) / range) * (height - padding * 2);
      return `${index === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <div className="equity-panel">
      <div className="panel-title">Equity curve</div>
      {values.length < 2 ? (
        <p className="panel-lead equity-empty">Waiting for the next agent cycle.</p>
      ) : (
        <svg className="equity-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Balance over time">
          <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} className="equity-axis" />
          <path d={path} className="equity-line" />
        </svg>
      )}
    </div>
  );
}

export default function ControlCenterPanel() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [pnl, setPnl] = useState<Record<string, any> | null>(null);
  const [riskUsage, setRiskUsage] = useState<Record<string, any> | null>(null);
  const [activity, setActivity] = useState<ActivityEntry[]>([]);
  const [balance, setBalance] = useState<Record<string, any> | null>(null);
  const [equityHistory, setEquityHistory] = useState<EquityPoint[]>([]);
  const [killSwitchEnabled, setKillSwitchEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [killSwitchLoading, setKillSwitchLoading] = useState(false);
  const [activityMode, setActivityMode] = useState<"autonomous" | "strategy">("autonomous");

  useEffect(() => {
    Promise.all([
      apiGet<any>("/positions"),
      apiGet<any>("/pnl"),
      apiGet<any>("/risk-usage"),
      apiGet<any>("/activity-log"),
      apiGet<any>("/kill-switch"),
      apiGet<any>("/account/balance"),
      apiGet<any>("/account/balance-history"),
    ])
      .then(([positionsData, pnlData, riskData, activityData, killData, balanceData, historyData]) => {
        setPositions(positionsData.positions ?? []);
        setPnl(pnlData);
        setRiskUsage(riskData);
        setActivity(activityData.entries ?? []);
        setKillSwitchEnabled(killData.enabled ?? false);
        setBalance(balanceData);
        setEquityHistory(historyData.points ?? []);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const handleKillSwitch = async () => {
    setKillSwitchLoading(true);
    try {
      const next = !killSwitchEnabled;
      await apiPost("/kill-switch", { enabled: next });
      setKillSwitchEnabled(next);
    } catch (err: any) {
      alert(`Couldn't update kill switch: ${err.message}`);
    } finally {
      setKillSwitchLoading(false);
    }
  };

  if (loading) {
    return <p className="panel-lead">Loading control center…</p>;
  }

  if (error) {
    return (
      <div className="strategy-empty">
        Couldn&apos;t load live data ({error}).
      </div>
    );
  }

  const dailyLossUsage = riskUsage?.usage_percent?.daily_loss ?? 0;
  const filteredActivity = activity
    .filter((entry) => (entry.mode ?? "autonomous") === activityMode)
    .slice(0, 8);

  return (
    <div>
      <div className="control-topline">
        <div
          className="status-pill"
          style={
            killSwitchEnabled
              ? { borderColor: "var(--down)", color: "var(--down)" }
              : {}
          }
        >
          <span
            className="status-dot"
            style={killSwitchEnabled ? { background: "var(--down)" } : {}}
          />
          {killSwitchEnabled ? "Stopped" : "Running"}
        </div>
        <div className="app-actions" style={{ marginTop: 0 }}>
          <button
            className="btn btn-danger"
            onClick={handleKillSwitch}
            disabled={killSwitchLoading}
          >
            {killSwitchLoading
              ? "Working…"
              : killSwitchEnabled
              ? "Resume"
              : "Kill switch"}
          </button>
        </div>
      </div>

      <div className="perf-row">
        <div className="perf-cell">
          <div className="perf-label">Total P&amp;L</div>
          <div className={`perf-value ${pnl?.total_pnl >= 0 ? "up" : "down"}`}>
            {pnl?.total_pnl >= 0 ? "+" : ""}${pnl?.total_pnl?.toFixed(2)}
          </div>
        </div>
        <div className="perf-cell">
          <div className="perf-label">Realized P&amp;L</div>
          <div className="perf-value">${pnl?.realized_pnl?.toFixed(2)}</div>
        </div>
        <div className="perf-cell">
          <div className="perf-label">Win rate</div>
          <div className="perf-value">
            {pnl?.win_rate_pct != null ? `${pnl.win_rate_pct}%` : "—"}
          </div>
        </div>
        <div className="perf-cell">
          <div className="perf-label">Max drawdown</div>
          <div className="perf-value down">
            {pnl?.max_drawdown_pct != null ? `-${pnl.max_drawdown_pct}%` : "—"}
          </div>
        </div>
      </div>

      <div className="equity-layout">
        <div className="balance-summary">
          <div className="perf-label">Current balance</div>
          <div className="balance-value">${Number(balance?.balance ?? balance?.current_balance ?? 0).toFixed(2)}</div>
          <div className={`balance-change ${(balance?.daily_change ?? 0) >= 0 ? "up" : "down"}`}>
            {(balance?.daily_change ?? 0) >= 0 ? "+" : ""}${Number(balance?.daily_change ?? 0).toFixed(2)} today
          </div>
        </div>
        <EquityCurve points={equityHistory} />
      </div>

      <div className="risk-row">
        <div className="risk-label-row">
          <span>Daily loss usage</span>
          <span>{dailyLossUsage}% of daily limit</span>
        </div>
        <div className="risk-bar">
          <div
            className="risk-bar-fill"
            style={{ width: `${Math.min(dailyLossUsage, 100)}%` }}
          />
        </div>
      </div>

      <div className="positions-section">
        <div className="panel-title">Positions</div>
        {positions.length === 0 ? (
          <div className="empty-state">
            <p className="empty-state-title">No open positions</p>
          </div>
        ) : (
          <table className="positions">
            <thead>
              <tr>
                <th>Asset</th>
                <th>Side</th>
                <th>Qty</th>
                <th>Notional</th>
                <th>P&amp;L</th>
                <th>Leverage</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p, i) => (
                <tr key={i}>
                  <td>{cleanSymbol(p.symbol)}</td>
                  <td>
                    <span
                      className={`side-tag ${p.side === "buy" ? "up" : "down"}`}
                    >
                      {p.side === "buy" ? "Long" : "Short"}
                    </span>
                  </td>
                  <td>{p.qty}</td>
                  <td>${p.notional_usd?.toFixed(2)}</td>
                  <td className={p.unrealized_pnl >= 0 ? "up" : "down"}>
                    {p.unrealized_pnl >= 0 ? "+" : ""}${p.unrealized_pnl?.toFixed(2)}
                  </td>
                  <td>{p.leverage}x</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="mode-activity-block">
        <div className="control-mode-center">
          <div className="mode-switch">
            <button
              className={activityMode === "autonomous" ? "active" : ""}
              onClick={() => setActivityMode("autonomous")}
            >
              Autonomous
            </button>
            <button
              className={activityMode === "strategy" ? "active" : ""}
              onClick={() => setActivityMode("strategy")}
            >
              Strategy
            </button>
          </div>
        </div>
        <div className="panel-title panel-title-center">
          Recent activity — <span>{activityMode === "autonomous" ? "Autonomous" : "Strategy"}</span>
        </div>
        <div className="activity-log">
          {filteredActivity.length === 0 ? (
            <p className="panel-lead" style={{ textAlign: "center" }}>
              No activity yet.
            </p>
          ) : (
            filteredActivity.map((entry) => (
              <div className="log-row" key={entry.id}>
                <span className="log-time">{timeAgo(entry.timestamp)}</span>
                <span>
                  {cleanSymbol(entry.symbol)} — {entry.action}
                  {entry.status === "skipped_existing_position"
                    ? " (position already open)"
                    : ""}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}