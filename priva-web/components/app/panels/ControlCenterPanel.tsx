"use client";

import { useRef, useState, useEffect } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { timeAgo, cleanSymbol } from "@/lib/format";

type Position = Record<string, any>;
type ActivityEntry = Record<string, any>;
type EquityPoint = {
  timestamp?: string;
  created_at?: string;
  balance?: number;
  equity?: number;
  futures_equity?: number | null;
  spot_equity?: number | null;
};

type ChartTimeframe = "hourly" | "daily" | "weekly" | "monthly";

function filterByTimeframe(points: EquityPoint[], timeframe: ChartTimeframe): EquityPoint[] {
  const buckets = new Map<string, EquityPoint>();

  for (const point of points) {
    const iso = point.timestamp ?? point.created_at;
    if (!iso) continue;
    const date = new Date(iso);
    const bucketKey = timeframe === "hourly"
      ? `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}-${date.getHours()}`
      : timeframe === "daily"
        ? `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`
        : timeframe === "weekly"
          ? String(Math.floor(date.getTime() / (7 * 24 * 60 * 60 * 1000)))
          : `${date.getFullYear()}-${date.getMonth()}`;
    const existing = buckets.get(bucketKey);
    if (!existing || new Date(iso).getTime() > new Date(existing.timestamp ?? existing.created_at ?? 0).getTime()) {
      buckets.set(bucketKey, point);
    }
  }

  return Array.from(buckets.values()).sort((a, b) => {
    const aTime = new Date(a.timestamp ?? a.created_at ?? 0).getTime();
    const bTime = new Date(b.timestamp ?? b.created_at ?? 0).getTime();
    return aTime - bTime;
  });
}

function executionLabel(entry: ActivityEntry): string {
  if (entry.status === "submitted" || entry.status === "closed") return "Executed";
  if (entry.status === "skipped_existing_position") return "Skipped: position already open";
  if (entry.status === "rejected") return "Rejected by exchange";
  if (entry.status === "risk_rejected") return "Rejected by risk check";
  return "Signal logged";
}

function EquityCurve({ points, market, valueKey }: { points: EquityPoint[]; market: "Futures" | "Spot"; valueKey: "futures_equity" | "spot_equity" }) {
  const [timeframe, setTimeframe] = useState<ChartTimeframe>("hourly");
  const [zoom, setZoom] = useState(1);
  const [isPanning, setIsPanning] = useState(false);
  const chartRef = useRef<HTMLDivElement>(null);
  const panRef = useRef({ startX: 0, startScrollLeft: 0 });
  const width = 720;
  const height = 260;
  const padding = { top: 12, right: 12, bottom: 28, left: 60 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;

  // Only plot points that carry a real value for this market. Snapshots are
  // written by two sources: the agent worker (combined balance only) and the
  // balance endpoint (combined + per-market breakdowns). Without this filter,
  // legacy/worker snapshots would punch the Spot curve down to $0 and mix
  // combined totals into the Futures curve.
  let chartPoints = filterByTimeframe(points, timeframe).filter((p) => p[valueKey] != null);
  if (chartPoints.length < 2 && valueKey === "futures_equity") {
    // Legacy snapshots only stored the combined balance; fall back to it so
    // the Futures curve still renders before per-market fields exist.
    chartPoints = filterByTimeframe(points, timeframe).filter((p) => p.balance != null || p.equity != null);
  }

  const hasMarketData = chartPoints.length > 0;
  const values = chartPoints.map((p) =>
    Number(
      valueKey === "futures_equity" && p[valueKey] == null
        ? p.balance ?? p.equity ?? 0
        : p[valueKey],
    ),
  );
  const times = chartPoints.map((p) => p.timestamp ?? p.created_at ?? "");

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
      : Array.from(
          new Set([0, Math.floor((values.length - 1) / 2), values.length - 1])
        );

  const formatTime = (iso: string) => {
    if (!iso) return "";
    const d = new Date(iso);
    if (timeframe === "hourly") {
      return `${d.toLocaleDateString(undefined, { month: "short", day: "numeric" })} ${d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`;
    }
    if (timeframe === "monthly") {
      return d.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
    }
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  };

  // Reset zoom/pan whenever the underlying dataset changes shape (timeframe
  // switch, or a different point count coming back from a refetch) so users
  // don't end up zoomed into empty space.
  useEffect(() => {
    setZoom(1);
    if (chartRef.current) chartRef.current.scrollLeft = 0;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeframe, values.length]);

  // Wheel zoom/pan is bound manually (not via onWheel) because React attaches
  // its root wheel listener as passive by default, which silently ignores
  // preventDefault() and lets the page scroll underneath the chart instead of
  // zooming it. Ctrl/Cmd+wheel zooms (matches the OS/browser zoom gesture and
  // trackpad pinch), Shift+wheel pans horizontally, plain wheel is left alone
  // so the page can still scroll normally when the cursor passes over the chart.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const onWheel = (event: WheelEvent) => {
      if (event.shiftKey) {
        event.preventDefault();
        chart.scrollLeft += event.deltaY;
        return;
      }

      if (!(event.ctrlKey || event.metaKey)) return; // let the page scroll normally

      event.preventDefault();
      const pointerX = event.clientX - chart.getBoundingClientRect().left;

      setZoom((oldScale) => {
        const nextScale = Math.min(4, Math.max(1, oldScale * Math.exp(-event.deltaY * 0.002)));
        if (nextScale === oldScale) return oldScale;

        const contentX = chart.scrollLeft + pointerX;
        requestAnimationFrame(() => {
          chart.scrollLeft = contentX * (nextScale / oldScale) - pointerX;
        });
        return nextScale;
      });
    };

    chart.addEventListener("wheel", onWheel, { passive: false });
    return () => chart.removeEventListener("wheel", onWheel);
  }, []);

  const handleChartPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    const chart = chartRef.current;
    if (!chart) return;
    panRef.current = { startX: event.clientX, startScrollLeft: chart.scrollLeft };
    chart.setPointerCapture(event.pointerId);
    setIsPanning(true);
  };

  const handleChartPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const chart = chartRef.current;
    if (!chart || !isPanning) return;
    chart.scrollLeft = panRef.current.startScrollLeft - (event.clientX - panRef.current.startX);
  };

  const stopChartPanning = (event: React.PointerEvent<HTMLDivElement>) => {
    const chart = chartRef.current;
    if (chart?.hasPointerCapture(event.pointerId)) chart.releasePointerCapture(event.pointerId);
    setIsPanning(false);
  };

  const resetView = () => {
    setZoom(1);
    if (chartRef.current) chartRef.current.scrollLeft = 0;
  };

  return (
    <div className="equity-panel">
      <div className="equity-chart-head">
        <div className="panel-title">{market} equity curve</div>
        <div className="equity-chart-tools">
          <div className="equity-timeframes" role="group" aria-label={`${market} chart timeframe`}>
            {(["hourly", "daily", "weekly", "monthly"] as const).map((option) => (
              <button
                key={option}
                type="button"
                className={timeframe === option ? "active" : ""}
                onClick={() => setTimeframe(option)}
              >
                {option === "hourly" ? "1H" : option === "daily" ? "1D" : option === "weekly" ? "7D" : "1M"}
              </button>
            ))}
          </div>
        </div>
      </div>
      {!hasMarketData || values.length < 2 ? (
        <p className="panel-lead equity-empty">Waiting for the next agent cycle.</p>
      ) : (
        <div
          ref={chartRef}
          className={`equity-scroll${isPanning ? " is-panning" : ""}`}
          onPointerDown={handleChartPointerDown}
          onPointerMove={handleChartPointerMove}
          onPointerUp={stopChartPanning}
          onPointerCancel={stopChartPanning}
          onDoubleClick={resetView}
          title="Ctrl/Cmd+scroll to zoom · Shift+scroll or drag to pan · double-click to reset"
        >
          <svg
            className="equity-chart"
            viewBox={`0 0 ${width} ${height}`}
            style={{ width: `${zoom * 100}%`, height: `${height}px` }}
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
  const [markets, setMarkets] = useState<Array<"spot" | "futures">>(["futures"]);
  const [modes, setModes] = useState<Array<"autonomous" | "strategy">>(["autonomous"]);
  const [marketSaving, setMarketSaving] = useState(false);
  const [marketError, setMarketError] = useState<string | null>(null);
  const loadVersionRef = useRef(0);

  const loadData = () => {
    const loadVersion = ++loadVersionRef.current;
    Promise.all([
      apiGet<any>("/positions"),
      apiGet<any>("/pnl"),
      apiGet<any>("/risk-usage"),
      apiGet<any>("/activity-log"),
      apiGet<any>("/kill-switch"),
      apiGet<any>("/account/balance"),
      apiGet<any>("/account/balance-history"),
      apiGet<any>("/user/agent-settings"),
    ])
      .then(([positionsData, pnlData, riskData, activityData, killData, balanceData, historyData, settingsData]) => {
        if (loadVersion !== loadVersionRef.current) return;
        setPositions(positionsData.positions ?? []);
        setPnl(pnlData);
        setRiskUsage(riskData);
        setActivity(activityData.entries ?? []);
        setKillSwitchEnabled(killData.enabled ?? false);
        setBalance(balanceData);
        setEquityHistory(historyData.points ?? []);
        if (Array.isArray(settingsData.execution_profiles) && settingsData.execution_profiles.length) {
          const nextMarkets = settingsData.execution_profiles
            .map((profile: string) => profile.split(":")[1])
            .filter((value: string): value is "spot" | "futures" => value === "spot" || value === "futures");
          const nextModes = settingsData.execution_profiles
            .map((profile: string) => profile.split(":")[0])
            .filter((value: string): value is "autonomous" | "strategy" => value === "autonomous" || value === "strategy");
          setMarkets(Array.from(new Set(nextMarkets)));
          setModes(Array.from(new Set(nextModes)));
        } else if (settingsData.market === "spot" || settingsData.market === "futures") {
          setMarkets([settingsData.market]);
        }
        setError(null);
        setLoading(false);
      })
      .catch((err) => {
        if (loadVersion !== loadVersionRef.current) return;
        setError(err.message);
        setLoading(false);
      });
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 15 * 1000);
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

  const handleExecutionChange = async (
    nextMarkets: Array<"spot" | "futures">,
    nextModes: Array<"autonomous" | "strategy">,
  ) => {
    if (!nextMarkets.length || !nextModes.length) return;
    const previousMarkets = markets;
    const previousModes = modes;
    setMarkets(nextMarkets);
    setModes(nextModes);
    setMarketSaving(true);
    setMarketError(null);
    try {
      await apiPost("/user/execution-settings", { markets: nextMarkets, modes: nextModes });
    } catch (err: any) {
      setMarkets(previousMarkets);
      setModes(previousModes);
      setMarketError(err.message);
    } finally {
      setMarketSaving(false);
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

  const dailyLossUsage = Math.max(0, Math.min(100, Number(riskUsage?.usage_percent?.daily_loss) || 0));
  const filteredActivity = activity
    .filter((entry) => (entry.mode ?? "autonomous") === activityMode)
    .sort((a, b) => new Date(b.timestamp ?? b.created_at ?? 0).getTime() - new Date(a.timestamp ?? a.created_at ?? 0).getTime())
    .slice(0, 8);

  return (
    <div>
      <div className="control-topline">
        <div className="control-status-group">
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
          <div className="market-control">
            <span className="market-control-label">Markets</span>
            <div className="mode-switch" aria-label="Trading market">
              {(["spot", "futures"] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  className={markets.includes(option) ? "active" : ""}
                  onClick={() => handleExecutionChange(
                    markets.includes(option) ? markets.filter((item) => item !== option) : [...markets, option],
                    modes,
                  )}
                  disabled={marketSaving || (markets.length === 1 && markets.includes(option))}
                >
                  {option === "spot" ? "Spot" : "Futures"}
                </button>
              ))}
            </div>
          </div>
          <div className="market-control">
            <span className="market-control-label">Modes</span>
            <div className="mode-switch" aria-label="Execution mode">
              {(["autonomous", "strategy"] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  className={modes.includes(option) ? "active" : ""}
                  onClick={() => handleExecutionChange(
                    markets,
                    modes.includes(option) ? modes.filter((item) => item !== option) : [...modes, option],
                  )}
                  disabled={marketSaving || (modes.length === 1 && modes.includes(option))}
                >
                  {option === "autonomous" ? "Autonomous" : "Strategy"}
                </button>
              ))}
            </div>
            {marketError ? <span className="market-control-error">{marketError}</span> : null}
          </div>
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
        <div className="equity-market-grid">
          <div className="market-equity-card">
            <div className="perf-label">Futures balance</div>
            <div className="market-balance-value">${Number(balance?.futures_equity ?? 0).toFixed(2)}</div>
            <div className={`balance-change ${(balance?.futures_daily_change ?? 0) >= 0 ? "up" : "down"}`}>
              {(balance?.futures_daily_change ?? 0) >= 0 ? "+" : ""}${Number(balance?.futures_daily_change ?? 0).toFixed(2)} today
            </div>
            <EquityCurve points={equityHistory} market="Futures" valueKey="futures_equity" />
          </div>
          <div className="market-equity-card">
            <div className="perf-label">Spot balance</div>
            <div className="market-balance-value">${Number(balance?.spot_equity ?? 0).toFixed(2)}</div>
            <div className={`balance-change ${(balance?.spot_daily_change ?? 0) >= 0 ? "up" : "down"}`}>
              {(balance?.spot_daily_change ?? 0) >= 0 ? "+" : ""}${Number(balance?.spot_daily_change ?? 0).toFixed(2)} today
            </div>
            <EquityCurve points={equityHistory} market="Spot" valueKey="spot_equity" />
          </div>
        </div>
      </div>

      <div className="perf-row" style={{ gridTemplateColumns: "repeat(2, 1fr)", marginBottom: 24 }}>
        <div className="perf-cell">
          <div className="perf-label">Futures equity</div>
          <div className="perf-value">${Number(balance?.futures_equity ?? 0).toFixed(2)}</div>
        </div>
        <div className="perf-cell">
          <div className="perf-label">Spot equity</div>
          <div className="perf-value">${Number(balance?.spot_equity ?? balance?.spot_usdt ?? 0).toFixed(2)}</div>
        </div>
      </div>

      <div className="risk-row">
        <div className="risk-label-row">
          <span>Today's risk used</span>
          <span>{dailyLossUsage}% of your daily loss limit</span>
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
              {positions.map((p) => (
                <tr key={p.position_id ?? p.id ?? `${p.symbol}-${p.side}`}>
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
                  <span className="log-status"> ({executionLabel(entry)})</span>
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}