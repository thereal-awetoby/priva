"use client";

import { useState, useMemo, useEffect } from "react";

type EventItem = {
  id: string;
  title: string;
  tag: "trade" | "risk" | "system" | "blocked";
  description: string;
  time: string;
  value: string;
  valueClass?: "up" | "down" | "";
  openedAt?: string;
};

type ActivityEntry = {
  id?: string;
  type?: string;
  symbol?: string;
  action?: string;
  status?: string;
  mode?: string;
  timestamp?: string | null;
  opened_at?: string | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8001";

const events: EventItem[] = [
  {
    id: "1",
    title: "Reduced NVDA-PERP",
    tag: "risk",
    description: "Volatility guard · 0.38 → 0.24 size",
    time: "2 min ago",
    value: "+$84.20",
    valueClass: "up",
  },
  {
    id: "2",
    title: "Opened AAPL spot",
    tag: "trade",
    description: "Momentum window · 12.4 shares",
    time: "18 min ago",
    value: "$2,178.40",
    valueClass: "",
  },
  {
    id: "3",
    title: "Heartbeat check",
    tag: "system",
    description: "All permissions within bounds",
    time: "42 min ago",
    value: "Clear",
    valueClass: "",
  },
  {
    id: "4",
    title: "Rebalanced BTC proxy",
    tag: "trade",
    description: "Core allocation · 4.8% drift",
    time: "1 hr ago",
    value: "+$31.08",
    valueClass: "up",
  },
  {
    id: "5",
    title: "Skipped TSLA entry",
    tag: "blocked",
    description: "Spread exceeded 0.42% limit",
    time: "3 hr ago",
    value: "Blocked",
    valueClass: "down",
  },
  {
    id: "6",
    title: "Strategy parameters updated",
    tag: "system",
    description: "Max position size · 18% → 15%",
    time: "5 hr ago",
    value: "You",
    valueClass: "",
  },
];

const tagIcons: Record<EventItem["tag"], React.ReactNode> = {
  risk: (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M7 1.5L12 3.2V6.8C12 9.8 9.8 11.7 7 12.4C4.2 11.7 2 9.8 2 6.8V3.2L7 1.5Z" stroke="currentColor" strokeWidth="1.1" strokeLinejoin="round" />
    </svg>
  ),
  trade: (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M7 1V13M3 4L7 1L11 4" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  system: (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.1" />
      <circle cx="7" cy="7" r="1.7" stroke="currentColor" strokeWidth="1.1" />
    </svg>
  ),
  blocked: (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M3 3L11 11M11 3L3 11" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" />
    </svg>
  ),
};

const filters: { id: "all" | EventItem["tag"]; label: string }[] = [
  { id: "all", label: "All" },
  { id: "trade", label: "Trade" },
  { id: "risk", label: "Risk" },
  { id: "system", label: "System" },
  { id: "blocked", label: "Blocked" },
];

export default function ActivityPanel() {
  const [activeFilter, setActiveFilter] = useState<"all" | EventItem["tag"]>("all");
  const [search, setSearch] = useState("");
  const [activityEvents, setActivityEvents] = useState<EventItem[]>(events);

  useEffect(() => {
    fetch(`${API_BASE}/activity-log`)
      .then((response) => {
        if (!response.ok) {
          throw new Error("Unable to load activity");
        }
        return response.json() as Promise<{ entries?: ActivityEntry[] }>;
      })
      .then((payload) => {
        const liveEvents = (payload.entries ?? []).map((entry, index): EventItem => {
          const isTrade = entry.type === "trade";
          const symbol = entry.symbol ?? "Unknown symbol";
          const action = entry.action ?? entry.type ?? "event";
          const timestamp = entry.timestamp ?? undefined;
          return {
            id: entry.id ?? `activity-${index}`,
            title: isTrade ? `${action === "buy" ? "Opened" : action} ${symbol}` : `${entry.type ?? "System"} ${symbol}`,
            tag: isTrade ? "trade" : entry.status === "rejected" ? "blocked" : "system",
            description: `${entry.mode ?? "autonomous"} mode · ${entry.status ?? "logged"}`,
            time: timestamp ? new Date(timestamp).toLocaleString() : "Time unavailable",
            value: entry.status ?? "Logged",
            valueClass: entry.status === "rejected" ? "down" : "",
            openedAt: entry.opened_at ?? undefined,
          };
        });
        if (liveEvents.length > 0) {
          setActivityEvents(liveEvents);
        }
      })
      .catch(() => undefined);
  }, []);

  const filteredEvents = useMemo(() => {
    return activityEvents.filter((e) => {
      const matchesFilter = activeFilter === "all" || e.tag === activeFilter;
      const matchesSearch =
        search.trim() === "" ||
        e.title.toLowerCase().includes(search.toLowerCase()) ||
        e.description.toLowerCase().includes(search.toLowerCase());
      return matchesFilter && matchesSearch;
    });
  }, [activeFilter, search, activityEvents]);

  return (
    <div>
      <div className="panel-eyebrow">Full transparency</div>
      <h2 className="panel-heading">Nothing happens in the dark.</h2>
      <p className="panel-lead">
        A human-readable record of every signal, decision, and order Priva
        considered.
      </p>

      <div className="activity-controls">
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
        <input
          className="activity-search"
          type="text"
          placeholder="Search decision log"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="event-list">
        {filteredEvents.length === 0 ? (
          <div className="empty-state">
            <p className="empty-state-title">No events match your filters</p>
            <p className="empty-state-sub">Try a different search or category</p>
          </div>
        ) : (
          filteredEvents.map((e) => (
            <div className="event-row" key={e.id}>
              <div className="event-icon">{tagIcons[e.tag]}</div>
              <div className="event-body">
                <div className="event-title-row">
                  <h4>{e.title}</h4>
                  <span className="event-tag">{e.tag}</span>
                </div>
                <p>{e.description}</p>
                {e.openedAt ? <p>Opened at {new Date(e.openedAt).toLocaleString()}</p> : null}
              </div>
              <div className="event-meta">
                <div className="event-time">{e.time}</div>
                <div className={e.valueClass}>{e.value}</div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}