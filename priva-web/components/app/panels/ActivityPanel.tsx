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

export default function ActivityPanel() {
  const [entries, setEntries] = useState<EventItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState("all");
    const [search, setSearch] = useState("");
    const [modeFilter, setModeFilter] = useState<"all" | "autonomous" | "strategy">("all");

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
              <input
                className="activity-search"
                type="text"
                placeholder="Search by symbol or action"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>

      <div className="event-list">
        {filteredEntries.length === 0 ? (
          <div className="empty-state">
            <p className="empty-state-title">No events match your filters</p>
            <p className="empty-state-sub">Try a different search or category</p>
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
                      : entry.status === "skipped_existing_position"
                        ? "Position already open"
                        : "Logged"}
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