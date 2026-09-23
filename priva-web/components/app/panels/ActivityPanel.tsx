"use client";

import { useState, useEffect, useMemo } from "react";
import { apiGet } from "@/lib/api";
import { timeAgo, cleanSymbol } from "@/lib/format";

type EventItem = Record<string, any>;

const filters = [
  { id: "all", label: "All" },
  { id: "buy", label: "Buy" },
  { id: "sell", label: "Sell" },
  { id: "hold", label: "Hold" },
  { id: "blocked", label: "Blocked" },
];

function getEventIcon(entry: EventItem) {
  if (entry.risk_check?.allowed === false) {
    return (
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
        <path d="M3 3L11 11M11 3L3 11" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" />
      </svg>
    );
  }
  if (entry.action === "buy" || entry.action === "sell") {
    return (
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
        <path d="M7 1V13M3 4L7 1L11 4" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.1" />
      <circle cx="7" cy="7" r="1.7" stroke="currentColor" strokeWidth="1.1" />
    </svg>
  );
}

function getEventTag(entry: EventItem): string {
  if (entry.risk_check?.allowed === false) return "blocked";
  return entry.action ?? "system";
}

/* ---------- Export modal ---------- */

type TimeRange = "7d" | "30d" | "90d" | "all";

const TIME_RANGES: { id: TimeRange; label: string }[] = [
  { id: "7d", label: "7 days" },
  { id: "30d", label: "30 days" },
  { id: "90d", label: "90 days" },
  { id: "all", label: "All time" },
];

function rangeStartMs(range: TimeRange): number | null {
  if (range === "all") return null;
  const days = range === "7d" ? 7 : range === "30d" ? 30 : 90;
  return Date.now() - days * 24 * 60 * 60 * 1000;
}

function entryDetails(entry: EventItem): string {
  if (entry.risk_check?.allowed === false) {
    return (entry.risk_check?.reasons ?? []).join(", ") || "Blocked by risk check";
  }
  if (entry.status === "skipped_existing_position") return "Position already open";
  if (entry.status === "rejected") return entry.message || "Rejected by exchange";
  return "";
}

function executionLabel(entry: EventItem): string {
  if (entry.status === "submitted" || entry.status === "closed") return "Executed";
  if (entry.status === "skipped_existing_position") return "Skipped: position already open";
  if (entry.status === "rejected") return "Rejected by exchange";
  if (entry.status === "risk_rejected") return "Rejected by risk check";
  return "Signal logged";
}

function csvEscape(value: string): string {
  if (/["\n\r]/.test(value)) return `"${value.replace(/"/g, '""')}"`;
  return value;
}

function buildCsv(rows: EventItem[]): string {
  const header = ["timestamp", "symbol", "action", "mode", "type", "status", "details"];
  const lines = rows.map((e) =>
    [
      e.timestamp ?? "",
      e.symbol ?? "",
      e.action ?? "",
      e.mode ?? "autonomous",
      getEventTag(e),
      e.status ?? "",
      entryDetails(e),
    ]
      .map((v) => csvEscape(String(v)))
      .join(",")
  );
  return [header.join(","), ...lines].join("\r\n");
}

function ExportModal({
  entries,
  onClose,
}: {
  entries: EventItem[];
  onClose: () => void;
}) {
  const symbols = useMemo(() => {
    const set = new Set<string>();
    entries.forEach((e) => e.symbol && set.add(cleanSymbol(e.symbol)));
    return Array.from(set).sort();
  }, [entries]);

  const [selectedSymbols, setSelectedSymbols] = useState<string[]>([]); // empty = all
  const [range, setRange] = useState<TimeRange>("all");

  const toggleSymbol = (s: string) =>
    setSelectedSymbols((prev) =>
      prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]
    );

  const startMs = rangeStartMs(range);

  const rows = useMemo(() => {
    return entries
      .filter((e) => {
        const matchesSymbol =
          selectedSymbols.length === 0 ||
          selectedSymbols.includes(cleanSymbol(e.symbol ?? ""));
        const ts = e.timestamp ? new Date(e.timestamp).getTime() : NaN;
        const matchesRange = startMs === null || (!Number.isNaN(ts) && ts >= startMs);
        return matchesSymbol && matchesRange;
      })
      .sort(
        (a, b) =>
          new Date(a.timestamp ?? 0).getTime() - new Date(b.timestamp ?? 0).getTime()
      );
  }, [entries, selectedSymbols, startMs]);

  const handleDownload = () => {
    const csv = buildCsv(rows);
    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `priva-activity-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose} aria-label="Close">
          Close ✕
        </button>
        <h2 className="modal-title">Export your activity</h2>
        <p className="modal-sub">
          Pick what you want in the file — everything else stays out.
        </p>

        <div className="form-field">
          <label className="form-label">Symbols</label>
          <div className="stock-toggle-list">
            <button
              type="button"
              className={`stock-chip ${selectedSymbols.length === 0 ? "active" : ""}`}
              onClick={() => setSelectedSymbols([])}
            >
              All
            </button>
            {symbols.map((s) => (
              <button
                key={s}
                type="button"
                className={`stock-chip ${selectedSymbols.includes(s) ? "active" : ""}`}
                onClick={() => toggleSymbol(s)}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <div className="form-field">
          <label className="form-label">Time range</label>
          <div className="mode-switch">
            {TIME_RANGES.map((r) => (
              <button
                key={r.id}
                className={range === r.id ? "active" : ""}
                onClick={() => setRange(r.id)}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>

        <div className="export-count">
          {rows.length} event{rows.length === 1 ? "" : "s"} will be in the file.
        </div>

        <div className="export-actions">
          <button className="btn" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn btn-primary"
            onClick={handleDownload}
            disabled={rows.length === 0}
          >
            Download CSV
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ActivityPanel() {
  const [entries, setEntries] = useState<EventItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState("all");
    const [search, setSearch] = useState("");
    const [modeFilter, setModeFilter] = useState<"all" | "autonomous" | "strategy">("all");
  const [isExportOpen, setIsExportOpen] = useState(false);

  useEffect(() => {
    apiGet<any>("/activity-log")
      .then((data) => {
        setEntries(data.entries ?? []);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const filteredEntries = useMemo(() => {
    return entries.filter((e) => {
      const tag = getEventTag(e);
      const matchesFilter = activeFilter === "all" || tag === activeFilter;
      const matchesMode =
        modeFilter === "all" || (e.mode ?? "autonomous") === modeFilter;
      const matchesSearch =
        search.trim() === "" ||
        (e.symbol ?? "").toLowerCase().includes(search.toLowerCase()) ||
        (e.action ?? "").toLowerCase().includes(search.toLowerCase());
      return matchesFilter && matchesMode && matchesSearch;
    });
  }, [entries, activeFilter, modeFilter, search]);

  if (loading) {
    return <p className="panel-lead">Loading activity…</p>;
  }

  if (error) {
    return (
      <div className="strategy-empty">
        Couldn&apos;t load activity ({error}).
      </div>
    );
  }

  return (
    <div>
      <div className="panel-eyebrow">Full transparency</div>
      <h2 className="panel-heading">Nothing happens in the dark.</h2>
      <p className="panel-lead">
        A human-readable record of every signal, decision, and order Priva
        considered.
      </p>

      <div className="activity-controls">
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          <div className="mode-switch">
            <button
              className={modeFilter === "all" ? "active" : ""}
              onClick={() => setModeFilter("all")}
            >
              All modes
            </button>
            <button
              className={modeFilter === "autonomous" ? "active" : ""}
              onClick={() => setModeFilter("autonomous")}
            >
              Autonomous
            </button>
            <button
              className={modeFilter === "strategy" ? "active" : ""}
              onClick={() => setModeFilter("strategy")}
            >
              Strategy
            </button>
          </div>
          <div className="mode-switch">
            {filters.map((f) => (
              <button
                key={f.id}
                className={activeFilter === f.id ? "active" : ""}
                onClick={() => setActiveFilter(f.id)}
              >
                {f.label}
              </button>
            ))}
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                      <input
                        className="activity-search"
                        type="text"
                        placeholder="Search AAPL, TSLA, buy, sell…"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                      />
                      <button className="btn export-btn" onClick={() => setIsExportOpen(true)}>
                        Export CSV
                      </button>
                    </div>
                  </div>

                  {isExportOpen && (
                    <ExportModal entries={entries} onClose={() => setIsExportOpen(false)} />
                  )}

                  <div className="event-list">
        {filteredEntries.length === 0 ? (
          <div className="empty-state">
                        <p className="empty-state-title">Nothing here yet</p>
            <p className="empty-state-sub">Try widening your filters or search</p>
          </div>
        ) : (
          filteredEntries.slice(0, 50).map((entry) => {
            const tag = getEventTag(entry);
            const blocked = tag === "blocked";
            return (
              <div className="event-row" key={entry.id}>
                <div className="event-icon">{getEventIcon(entry)}</div>
                <div className="event-body">
                  <div className="event-title-row">
                    <h4>
                      {cleanSymbol(entry.symbol)} — {entry.action ?? "cycle"}
                    </h4>
                    <span className="event-tag">{tag}</span>
                    {entry.mode && (
                      <span className="event-tag">{entry.mode}</span>
                    )}
                  </div>
                  <p>
                    {blocked
                      ? (entry.risk_check?.reasons ?? []).join(", ") || "Blocked by risk check"
                      : executionLabel(entry)}
                  </p>
                </div>
                <div className="event-meta">
                  <div className="event-time">{timeAgo(entry.timestamp)}</div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}