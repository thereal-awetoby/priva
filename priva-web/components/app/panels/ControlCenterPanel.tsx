"use client";

import { useState, useEffect } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { timeAgo, cleanSymbol } from "@/lib/format";

type Position = Record<string, any>;
type ActivityEntry = Record<string, any>;
type EquityPoint = { timestamp?: string; created_at?: string; balance?: number; equity?: number };

function bucketByHour(points: EquityPoint[]): EquityPoint[] {
  const buckets = new Map<string, EquityPoint>();

  for (const point of points) {
    const iso = point.timestamp ?? point.created_at;
    if (!iso) continue;
    const date = new Date(iso);
    // Key = year-month-day-hour, so every point within the same hour collapses together
    const hourKey = `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}-${date.getHours()}`;

    const existing = buckets.get(hourKey);
    // Keep the LATEST snapshot within that hour (closest to "end of the hour")
    if (!existing || new Date(iso).getTime() > new Date(existing.timestamp ?? existing.created_at ?? 0).getTime()) {
      buckets.set(hourKey, point);
    }
  }

  return Array.from(buckets.values()).sort((a, b) => {
    const aTime = new Date(a.timestamp ?? a.created_at ?? 0).getTime();
    const bTime = new Date(b.timestamp ?? b.created_at ?? 0).getTime();
    return aTime - bTime;
  });
}

function EquityCurve({ points }: { points: EquityPoint[] }) {
  const pointWidth = 40; // pixels per data point — controls how "zoomed in" the chart is
  const width = Math.max(720, points.length * pointWidth);
  const height = 200;
  const padding = { top: 12, right: 12, bottom: 28, left: 60 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;

  const values = points.map((p) => Number(p.balance ?? p.equity ?? 0));
  const times = points.map((p) => p.timestamp ?? p.created_at ?? "");

  const min = values.length ? Math.min(...values) : 0;
  const max = values.length ? Math.max(...values) : 1;
  const range = max - min || 1;

  const xFor = (i: number) =>
    padding.left + (i / Math.max(values.length - 1, 1)) * plotW;
  const yFor = (v: number) =>
    padding.top + plotH - ((v - min) / range) * plotH;

  const path = values
    .map((v, i) => `${i === 0 ? "M" : "L"} ${xFor(i).toFixed(1)} ${yFor(v).toFixed(1)}`)
    .join(" ");

  const yTicks = [min, min + range / 2, max];
  const tickIndexes =
    values.length <= 1
      ? []
      : [0, Math.floor((values.length - 1) / 2), values.length - 1];

  const formatTime = (iso: string) => {
    if (!iso) return "";
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  };

  return (
    <div className="equity-panel">
      <div className="panel-title">Equity curve</div>
      {values.length < 2 ? (
        <p className="panel-lead equity-empty">Waiting for the next agent cycle.</p>
            ) : (
        <div className="equity-scroll">
        <svg
          className="equity-chart"
          viewBox={`0 0 ${width} ${height}`}
          style={{ width: `${width}px`, height: `${height}px` }}
          role="img"
          aria-label="Balance over time"
        >
          {yTicks.map((v, i) => (
            <g key={i}>
              <line
                x1={padding.left}
                y1={yFor(v)}
                x2={width - padding.right}
                y2={yFor(v)}
                className="equity-gridline"
              />
              <text x={padding.left - 8} y={yFor(v)} className="equity-axis-label" textAnchor="end" dominantBaseline="middle">
                ${v.toFixed(0)}
              </text>
            </g>
          ))}
          {tickIndexes.map((i) => (
            <text
              key={i}
              x={xFor(i)}
              y={height - padding.bottom + 18}
              className="equity-axis-label"
              textAnchor="middle"
            >
              {formatTime(times[i])}
            </text>
          ))}
                    <path d={path} className="equity-line" />
        </svg>
        </div>
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

    const loadData = () => {
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
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 6 * 60 * 60 * 1000);
    return () => clearInterval(interval);
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
        <EquityCurve points={bucketByHour(equityHistory)} />
              </div>

              <div className="perf-row" style={{ gridTemplateColumns: "repeat(2, 1fr)", marginBottom: 24 }}>
                <div className="perf-cell">
                  <div className="perf-label">Futures equity</div>
                  <div className="perf-value">${Number(balance?.futures_equity ?? 0).toFixed(2)}</div>
                </div>
                <div className="perf-cell">
                  <div className="perf-label">Spot USDT</div>
                  <div className="perf-value">${Number(balance?.spot_usdt ?? 0).toFixed(2)}</div>
                </div>
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