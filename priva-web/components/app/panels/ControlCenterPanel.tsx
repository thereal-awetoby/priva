"use client";

import { useRef, useState, useEffect, useLayoutEffect, useId } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { formatActivityTime, timeAgo, cleanSymbol } from "@/lib/format";
import PositionDetailModal from "@/components/app/PositionDetailModal";

type Position = Record<string, any>;
type ActivityEntry = Record<string, any>;
type EquityPoint = {
  timestamp?: string;
  created_at?: string;
  balance?: number;
  equity?: number;
  futures_equity?: number | null;
  spot_equity?: number | null;
  futures_equity_carried?: boolean;
  spot_equity_carried?: boolean;
};

type ChartTimeframe = "minute" | "hourly" | "daily" | "weekly" | "monthly";
type HoverInfo = { value: number; time: string } | null;

function aggregateByTimeframe(points: EquityPoint[], timeframe: ChartTimeframe): EquityPoint[] {
  const validPoints = points
    .map((point) => ({ point, time: new Date(point.timestamp ?? point.created_at ?? 0).getTime() }))
    .filter(({ time }) => Number.isFinite(time));
  if (!validPoints.length) return [];

  const buckets = new Map<string, {
    point: EquityPoint;
    latestTime: number;
    latestFuturesTime: number;
    latestSpotTime: number;
  }>();

  for (const { point, time } of validPoints) {
    const date = new Date(time);
    let bucketKey: string;
    if (timeframe === "minute") {
      bucketKey = `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}-${date.getHours()}-${date.getMinutes()}`;
    } else if (timeframe === "hourly") {
      bucketKey = `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}-${date.getHours()}`;
    } else if (timeframe === "daily") {
      bucketKey = `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
    } else if (timeframe === "weekly") {
      const weekStart = new Date(date);
      const daysSinceMonday = (date.getDay() + 6) % 7;
      weekStart.setDate(date.getDate() - daysSinceMonday);
      bucketKey = `${weekStart.getFullYear()}-${weekStart.getMonth()}-${weekStart.getDate()}`;
    } else {
      bucketKey = `${date.getFullYear()}-${date.getMonth()}`;
    }
    const existing = buckets.get(bucketKey);
    if (!existing) {
      buckets.set(bucketKey, {
        point: { ...point },
        latestTime: time,
        latestFuturesTime: point.futures_equity != null ? time : -Infinity,
        latestSpotTime: point.spot_equity != null ? time : -Infinity,
      });
      continue;
    }
    if (time > existing.latestTime) {
      existing.latestTime = time;
      existing.point.timestamp = point.timestamp ?? point.created_at;
      existing.point.created_at = point.created_at;
      existing.point.balance = point.balance;
      existing.point.equity = point.equity;
    }
    if (point.futures_equity != null && time >= existing.latestFuturesTime) {
      existing.latestFuturesTime = time;
      existing.point.futures_equity = point.futures_equity;
    }
    if (point.spot_equity != null && time >= existing.latestSpotTime) {
      existing.latestSpotTime = time;
      existing.point.spot_equity = point.spot_equity;
    }
  }

  const bucketPoints = Array.from(buckets.values()).map(({ point }) => point).sort((a, b) => {
    const aTime = new Date(a.timestamp ?? a.created_at ?? 0).getTime();
    const bTime = new Date(b.timestamp ?? b.created_at ?? 0).getTime();
    return aTime - bTime;
  });

  let lastFuturesEquity: number | undefined;
  let lastSpotEquity: number | undefined;
  return bucketPoints.map((point) => {
    const nextPoint = { ...point, futures_equity_carried: false, spot_equity_carried: false };
    if (nextPoint.futures_equity != null) {
      lastFuturesEquity = Number(nextPoint.futures_equity);
    } else if (lastFuturesEquity != null) {
      nextPoint.futures_equity = lastFuturesEquity;
      nextPoint.futures_equity_carried = true;
    }
    if (nextPoint.spot_equity != null) {
      lastSpotEquity = Number(nextPoint.spot_equity);
    } else if (lastSpotEquity != null) {
      nextPoint.spot_equity = lastSpotEquity;
      nextPoint.spot_equity_carried = true;
    }
    return nextPoint;
  });
}

// Date + time label used for the hover readout (chart tooltip and card header).
function formatHoverTime(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  return `${d.toLocaleDateString(undefined, { day: "numeric", month: "short" })} ${d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`;
}

function EquityCurve({
  points,
  market,
  valueKey,
  onHover,
}: {
  points: EquityPoint[];
  market: "Futures" | "Spot";
  valueKey: "futures_equity" | "spot_equity";
  onHover?: (info: HoverInfo) => void;
}) {
  const uid = useId().replace(/:/g, "");
  const [timeframe, setTimeframe] = useState<ChartTimeframe>("hourly");
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const shellRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(720);
  const height = 260;
  const padding = { top: 12, right: 12, bottom: 28, left: 60 };

  // Keep the complete aggregated timeline for every resolution. Worker
  // snapshots can be market-specific, so a missing market field is a genuine
  // gap and must not be replaced with the generic balance value.
  const chartPoints = aggregateByTimeframe(points, timeframe);
  const values = chartPoints.map((point): number | null => {
    if (point[valueKey] != null) return Number(point[valueKey]);
    return null;
  });
  const numericValues = values.filter((value): value is number => value != null && Number.isFinite(value));
  const hasMarketData = numericValues.length > 0;
  const hasBuckets = chartPoints.length > 0;
  // True only while the chart block is actually in the DOM. The resize
  // observer below depends on it so it re-binds when the chart appears after
  // an empty state (e.g. Spot chart receiving its first data).
  const chartMounted = hasBuckets && hasMarketData;
  const carriedValues = chartPoints.map((point) => valueKey === "futures_equity"
    ? Boolean(point.futures_equity_carried)
    : Boolean(point.spot_equity_carried));
  const times = chartPoints.map((p) => p.timestamp ?? p.created_at ?? "");
  const timeMs = times.map((t) => new Date(t).getTime());

  // Real time axis: points are positioned by when they happened, not by their
  // position in the list, so a long gap in the data is drawn as a long gap.
  const firstT = timeMs[0] ?? 0;
  const lastT = timeMs[timeMs.length - 1] ?? 1;
  const spanT = lastT - firstT || 1;
  const gapSizes = timeMs.slice(1).map((t, i) => t - timeMs[i]).filter((g) => g > 0).sort((a, b) => a - b);
  const medianGap = gapSizes.length ? gapSizes[Math.floor(gapSizes.length / 2)] : 0;
  const gapThresholdMs = medianGap * 4;

  // The chart always fits its card: no zoom, no horizontal scrolling.
  const svgWidth = containerWidth;
  const plotW = svgWidth - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;

  const min = numericValues.length ? Math.min(...numericValues) : 0;
  const max = numericValues.length ? Math.max(...numericValues) : 1;
  const range = max - min || 1;

  const xFor = (i: number) => padding.left + ((timeMs[i] - firstT) / spanT) * plotW;
  const yFor = (v: number) => padding.top + plotH - ((v - min) / range) * plotH;

  const realPaths: string[] = [];
  const carriedPaths: string[] = [];
  const gapPaths: string[] = [];
  let previousPoint: { index: number; value: number } | null = null;
  values.forEach((value, index) => {
    if (value == null) {
      previousPoint = null;
      return;
    }
    if (previousPoint && previousPoint.index === index - 1) {
      const segment = `M ${xFor(previousPoint.index).toFixed(1)} ${yFor(previousPoint.value).toFixed(1)} L ${xFor(index).toFixed(1)} ${yFor(value).toFixed(1)}`;
      const isGap = medianGap > 0 && timeMs[index] - timeMs[previousPoint.index] > gapThresholdMs;
      if (isGap) gapPaths.push(segment);
      else (carriedValues[index] ? carriedPaths : realPaths).push(segment);
    }
    previousPoint = { index, value };
  });

  const yTicks = [min, max];
  const estimatedLabelWidth = timeframe === "minute" || timeframe === "hourly" ? 150 : 105;
  const maxTickLabels = Math.max(2, Math.floor(plotW / estimatedLabelWidth));
  const finiteTimeIndexes = timeMs
    .map((timestamp, index) => ({ timestamp, index }))
    .filter(({ timestamp }) => Number.isFinite(timestamp));
  const tickCount = Math.min(maxTickLabels, finiteTimeIndexes.length);
  const resolvedTickIndexes = tickCount <= 1
    ? finiteTimeIndexes.slice(0, tickCount).map(({ index }) => index)
    : Array.from({ length: tickCount }, (_, index) => (
        finiteTimeIndexes.reduce((nearest, candidate) => {
          const targetTime = firstT + (lastT - firstT) * index / (tickCount - 1);
          return Math.abs(candidate.timestamp - targetTime) < Math.abs(nearest.timestamp - targetTime)
            ? candidate
            : nearest;
        }).index
      ));
  const tickIndexes = Array.from(new Set(resolvedTickIndexes));

  const formatTime = (iso: string) => {
    if (!iso) return "";
    const d = new Date(iso);
    if (timeframe === "minute" || timeframe === "hourly") {
      return `${d.toLocaleDateString(undefined, { month: "short", day: "numeric" })} ${d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`;
    }
    if (timeframe === "monthly") {
      return d.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
    }
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  };

  // Measure the chart shell. Re-binds whenever the chart block mounts or
  // unmounts, so a chart that starts in an empty state still gets measured.
  useLayoutEffect(() => {
    const shell = shellRef.current;
    if (!shell) return;
    const observer = new ResizeObserver(() => setContainerWidth(shell.clientWidth));
    observer.observe(shell);
    setContainerWidth(shell.clientWidth);
    return () => observer.disconnect();
  }, [chartMounted]);

  // Single place that updates the hovered point and tells the parent card, so
  // the big balance number above the chart can follow the cursor.
  const updateHover = (index: number | null) => {
    setHoverIndex(index);
    if (!onHover) return;
    const value = index != null ? values[index] : null;
    if (index == null || value == null) onHover(null);
    else onHover({ value, time: times[index] });
  };

  // Cursor tracking: snap to the data point closest to the cursor's x.
  const handlePointerMove = (event: React.PointerEvent<SVGSVGElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const cursorX = event.clientX - rect.left;
    let bestIndex: number | null = null;
    let bestDistance = Infinity;
    for (let i = 0; i < values.length; i++) {
      if (values[i] == null) continue;
      const distance = Math.abs(xFor(i) - cursorX);
      if (distance < bestDistance) {
        bestDistance = distance;
        bestIndex = i;
      }
    }
    updateHover(bestIndex);
  };
  const clearHover = () => updateHover(null);

  // Make sure the parent never keeps showing a stale hover if this chart unmounts.
  useEffect(() => {
    return () => onHover?.(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const hoverValue = hoverIndex != null ? values[hoverIndex] : null;
  const hoverX = hoverIndex != null && hoverValue != null ? xFor(hoverIndex) : null;
  const hoverY = hoverValue != null ? yFor(hoverValue) : null;

  const lines = (
    <>
      {realPaths.map((segment, index) => <path key={`real-${index}`} d={segment} className="equity-line" />)}
      {carriedPaths.map((segment, index) => <path key={`carried-${index}`} d={segment} className="equity-line equity-line-carried" />)}
      {gapPaths.map((segment, index) => (
        <path key={`gap-${index}`} d={segment} className="equity-line" strokeDasharray="4 4" opacity={0.5} />
      ))}
    </>
  );

  return (
    <div className="equity-panel">
      <div className="equity-chart-head">
        <div className="panel-title">{market} equity curve</div>
        <div className="equity-chart-tools">
          <div className="equity-timeframes" role="group" aria-label={`${market} chart timeframe`}>
            {(["minute", "hourly", "daily", "weekly", "monthly"] as const).map((option) => (
              <button
                key={option}
                type="button"
                className={timeframe === option ? "active" : ""}
                onClick={() => {
                  setTimeframe(option);
                  updateHover(null);
                }}
              >
                {option === "minute" ? "1m" : option === "hourly" ? "1H" : option === "daily" ? "1D" : option === "weekly" ? "7D" : "1M"}
              </button>
            ))}
          </div>
        </div>
      </div>
      {!hasBuckets ? (
        <p className="panel-lead equity-empty">Waiting for the next agent cycle.</p>
      ) : !hasMarketData ? (
        <p className="panel-lead equity-empty">Data is available, but no {market.toLowerCase()} equity values exist in this range.</p>
      ) : (
        <div className="equity-chart-shell" ref={shellRef} style={{ position: "relative" }}>
          <svg
            className="equity-chart"
            width={svgWidth}
            height={height}
            viewBox={`0 0 ${svgWidth} ${height}`}
            style={{ display: "block", cursor: "crosshair", touchAction: "pan-y" }}
            role="img"
            aria-label={`${market} balance over time`}
            onPointerMove={handlePointerMove}
            onPointerDown={handlePointerMove}
            onPointerLeave={clearHover}
            onPointerCancel={clearHover}
          >
            <defs>
              {/* Everything left of the cursor stays bright; the rest is dimmed. */}
              <clipPath id={`${uid}-past`}>
                <rect x={0} y={0} width={hoverX ?? svgWidth} height={height} />
              </clipPath>
            </defs>

            {yTicks.map((v, i) => (
              <g key={i}>
                <line
                  x1={padding.left}
                  y1={yFor(v)}
                  x2={svgWidth - padding.right}
                  y2={yFor(v)}
                  className="equity-gridline"
                />
                <text
                  x={padding.left - 8}
                  y={yFor(v)}
                  className="equity-axis-label"
                  textAnchor="end"
                  dominantBaseline="middle"
                >
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
                textAnchor={i === 0 ? "start" : i === values.length - 1 ? "end" : "middle"}
              >
                {formatTime(times[i])}
              </text>
            ))}

            {hoverX != null ? (
              <>
                <g opacity={0.35}>{lines}</g>
                <g clipPath={`url(#${uid}-past)`}>{lines}</g>
              </>
            ) : (
              <g>{lines}</g>
            )}

            {hoverX != null && hoverY != null ? (
              <>
                <line
                  x1={hoverX}
                  y1={padding.top}
                  x2={hoverX}
                  y2={height - padding.bottom}
                  className="equity-gridline"
                />
                <circle
                  cx={hoverX}
                  cy={hoverY}
                  r={4.5}
                  className="equity-line"
                  style={{ fill: "var(--bg-sunken)", strokeWidth: 2 }}
                />
              </>
            ) : null}
          </svg>

          {hoverX != null && hoverValue != null && hoverIndex != null ? (
            <div
              className="equity-tooltip"
              style={{
                position: "absolute",
                top: 0,
                left: Math.min(Math.max(hoverX, 80), svgWidth - 80),
                transform: "translateX(-50%)",
                padding: "4px 8px",
                background: "var(--bg-sunken)",
                border: "1px solid currentColor",
                fontSize: 12,
                whiteSpace: "nowrap",
                pointerEvents: "none",
                zIndex: 2,
              }}
            >
              <div>{formatHoverTime(times[hoverIndex])}</div>
              <div>${hoverValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}

export default function ControlCenterPanel() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [pnl, setPnl] = useState<Record<string, any> | null>(null);
  const [riskUsage, setRiskUsage] = useState<Record<string, any> | null>(null);
  const [statusData, setStatusData] = useState<Record<string, any> | null>(null);
  const [activity, setActivity] = useState<ActivityEntry[]>([]);
  const [balance, setBalance] = useState<Record<string, any> | null>(null);
  const [equityHistory, setEquityHistory] = useState<EquityPoint[]>([]);
  const [killSwitchEnabled, setKillSwitchEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [killSwitchLoading, setKillSwitchLoading] = useState(false);
  const [activityMode, setActivityMode] = useState<"autonomous" | "strategy">("autonomous");
  const [selectedPosition, setSelectedPosition] = useState<Record<string, any> | null>(null);
  const [markets, setMarkets] = useState<Array<"spot" | "futures">>(["futures"]);
  const [modes, setModes] = useState<Array<"autonomous" | "strategy">>(["autonomous"]);
  const [marketSaving, setMarketSaving] = useState(false);
  const [marketError, setMarketError] = useState<string | null>(null);
  const [futuresHover, setFuturesHover] = useState<HoverInfo>(null);
  const [spotHover, setSpotHover] = useState<HoverInfo>(null);
  const [killSwitchNotice, setKillSwitchNotice] = useState<string | null>(null);
  const previousKillSwitchRef = useRef<boolean | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const loadVersionRef = useRef(0);

  const loadData = (attempt = 0) => {
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
      apiGet<any>("/status"),
    ])
      .then(([positionsData, pnlData, riskData, activityData, killData, balanceData, historyData, settingsData, statusResponse]) => {
        if (loadVersion !== loadVersionRef.current) return;
        setPositions(positionsData.positions ?? []);
        setPnl(pnlData);
        setRiskUsage(riskData);
        setStatusData(statusResponse);
        setActivity(activityData.entries ?? []);
        setKillSwitchEnabled(killData.enabled ?? false);
        if (previousKillSwitchRef.current !== null && previousKillSwitchRef.current !== killData.enabled) {
          setKillSwitchNotice(killData.enabled ? "Kill switch engaged · Agent paused" : "Kill switch released · Agent restarted");
        }
        previousKillSwitchRef.current = Boolean(killData.enabled);
        setBalance(balanceData);
        setEquityHistory([
          ...(historyData.points ?? []),
          {
            timestamp: new Date().toISOString(),
            balance: Number(balanceData.balance ?? balanceData.current_balance ?? 0),
            equity: Number(balanceData.balance ?? balanceData.current_balance ?? 0),
            futures_equity: balanceData.futures_equity != null ? Number(balanceData.futures_equity) : null,
            spot_equity: balanceData.spot_equity != null ? Number(balanceData.spot_equity) : null,
          },
        ]);
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
        if (attempt === 0) {
          window.setTimeout(() => loadData(1), 500);
          return;
        }
        setError(err.message);
        setLoading(false);
      });
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(() => loadData(), 15 * 1000);
    const handleVisibility = () => {
      if (document.visibilityState === "visible") loadData();
    };
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, []);

  useEffect(() => {
    const clock = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(clock);
  }, []);

  const handleKillSwitch = async () => {
    setKillSwitchLoading(true);
    try {
      const next = !killSwitchEnabled;
      await apiPost("/kill-switch", { enabled: next });
      setKillSwitchEnabled(next);
      setKillSwitchNotice(next ? "Kill switch engaged · Agent paused" : "Kill switch released · Agent restarted");
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
  const watchedSymbols = (statusData?.watched_symbols ?? []).map((symbol: string) => symbol.replace(/USDT$/, ""));
  const watchLine = watchedSymbols.length ? `Watching ${watchedSymbols.join(" & ")}` : "Watching";
  const lastCycle = statusData?.last_cycle ? new Date(statusData.last_cycle).getTime() : null;
  const intervalSeconds = statusData?.cycle_interval_seconds;
  const remainingSeconds = lastCycle && intervalSeconds != null
    ? Math.max(0, Math.ceil((lastCycle + Number(intervalSeconds) * 1000 - now) / 1000))
    : null;
  const cycleLine = remainingSeconds != null
    ? `${watchLine} · Next cycle in ${Math.floor(remainingSeconds / 60)}m ${remainingSeconds % 60}s`
    : watchLine;
  const statusLine = statusData?.agent_state === "offline" ? `Agent offline · ${cycleLine}` : cycleLine;
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
          <div className="status-line">{statusLine}</div>
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
      {killSwitchNotice ? <div className="panel-lead">{killSwitchNotice}</div> : null}
      {statusData?.daily_loss_usage_pct != null && Number(statusData.daily_loss_usage_pct) > 70 ? (
        <div className="panel-lead">Risk usage elevated · {Math.round(Number(statusData.daily_loss_usage_pct))}% of daily loss limit</div>
      ) : null}

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
            <div className="market-balance-value">
              ${(futuresHover?.value ?? Number(balance?.futures_equity ?? 0)).toFixed(2)}
            </div>
            {futuresHover ? (
              <div className="balance-change">{formatHoverTime(futuresHover.time)}</div>
            ) : (
              <div className={`balance-change ${(balance?.futures_daily_change ?? 0) >= 0 ? "up" : "down"}`}>
                {(balance?.futures_daily_change ?? 0) >= 0 ? "+" : ""}${Number(balance?.futures_daily_change ?? 0).toFixed(2)} today
              </div>
            )}
            <EquityCurve points={equityHistory} market="Futures" valueKey="futures_equity" onHover={setFuturesHover} />
          </div>
          <div className="market-equity-card">
            <div className="perf-label">Spot balance</div>
            <div className="market-balance-value">
              ${(spotHover?.value ?? Number(balance?.spot_equity ?? 0)).toFixed(2)}
            </div>
            {spotHover ? (
              <div className="balance-change">{formatHoverTime(spotHover.time)}</div>
            ) : (
              <div className={`balance-change ${(balance?.spot_daily_change ?? 0) >= 0 ? "up" : "down"}`}>
                {(balance?.spot_daily_change ?? 0) >= 0 ? "+" : ""}${Number(balance?.spot_daily_change ?? 0).toFixed(2)} today
              </div>
            )}
            <EquityCurve points={equityHistory} market="Spot" valueKey="spot_equity" onHover={setSpotHover} />
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
                <th></th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => (
                <tr key={p.position_id ?? p.id ?? `${p.symbol}-${p.side}`} onClick={() => setSelectedPosition(p)} className="position-row">
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
                  <td>
                    <span className="position-expand-arrow">
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <path d="M5 3L9 7L5 11" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    </span>
                  </td>
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
            filteredActivity.map((entry) => {
              const eventTimestamp = entry.status === "closed"
                ? entry.closed_at
                : entry.opened_at ?? entry.timestamp;
              const activityTime = formatActivityTime(eventTimestamp);
              return (
                <div className="log-row" key={entry.id}>
                  <time className="log-time" dateTime={eventTimestamp ?? undefined} title={activityTime.title}>
                    {activityTime.display}
                  </time>
                  <span>
                    {cleanSymbol(entry.symbol)} — {entry.action}
                    <span className="log-status"> ({entry.display_label})</span>
                  </span>
                </div>
              );
            })
          )}
        </div>
      </div>

      {selectedPosition && (
        <PositionDetailModal
          position={selectedPosition}
          onClose={() => setSelectedPosition(null)}
        />
      )}
    </div>
  );
}