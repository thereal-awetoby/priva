"use client";

import { useState, useEffect, useRef } from "react";
import { apiGet } from "@/lib/api";
import { timeAgo, cleanSymbol } from "@/lib/format";

type EventItem = Record<string, any>;

const SEEN_KEY = "priva_notifications_last_seen";

// Mirrors exactly what backend/app/main.py's _activity_entry() considers a
// real position event: opened_at is only ever set when status === "submitted",
// closed_at only when status === "closed". Checking action alone (buy/sell/close)
// isn't enough — an exchange-rejected order still has action "buy" but status
// "rejected", and would otherwise show up here as a fake "Long opened".
function isPositionEvent(entry: EventItem): boolean {
  if (entry.status === "closed") return true;
  if (entry.status === "submitted") {
    return entry.action === "buy" || entry.action === "sell";
  }
  return false;
}

// The timestamp that actually matters for a row: when it opened, or when
// it closed — same convention ActivityPanel uses, so "20m ago" here
// matches "20m ago" there for the same event.
function eventTimestampOf(entry: EventItem): string | undefined {
  return entry.status === "closed"
    ? entry.closed_at ?? entry.timestamp
    : entry.opened_at ?? entry.timestamp;
}

// Same fields ActivityPanel's eventUnits/eventPrice/eventPositionSize read —
// backend/app/main.py's _activity_entry() puts these directly on the entry.
function statsLine(entry: EventItem): string {
  const parts: string[] = [];
  if (entry.units != null) parts.push(`${entry.units} units`);
  if (entry.price != null) parts.push(`@ $${Number(entry.price).toFixed(4)}`);
  if (entry.position_size_usd != null) {
    parts.push(`$${Number(entry.position_size_usd).toFixed(2)} notional`);
  }
  return parts.join(" · ");
}

// PnL is only meaningful (and only ever present) on closed rows — see the
// note in _activity_entry(): it's exchange-reported-only for now, so most
// closed rows will render "PnL —" rather than a number. That's expected,
// not a bug — it's the same behavior ActivityPanel's event rows show.
function pnlText(entry: EventItem): string | null {
  if (entry.status !== "closed") return null;
  return entry.pnl != null ? Number(entry.pnl).toFixed(2) : "";
}

export default function NotificationBell() {
  const [entries, setEntries] = useState<EventItem[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [lastSeen, setLastSeen] = useState<number>(0);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    apiGet<any>("/activity-log")
      .then((data) => setEntries(data.entries ?? []))
      .catch(() => setEntries([]));

    try {
      const stored = localStorage.getItem(SEEN_KEY);
      if (stored) setLastSeen(Number(stored));
    } catch {
      // localStorage unavailable — badge will just always show total count
    }
  }, []);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const positionEvents = entries
    .filter(isPositionEvent)
    .sort(
      (a, b) =>
        new Date(eventTimestampOf(b) ?? 0).getTime() -
        new Date(eventTimestampOf(a) ?? 0).getTime()
    )
    .slice(0, 20);

  const unseenCount = positionEvents.filter((e) => {
    const ts = eventTimestampOf(e);
    return ts != null && new Date(ts).getTime() > lastSeen;
  }).length;

  const handleToggle = () => {
    const next = !isOpen;
    setIsOpen(next);
    if (next) {
      const now = Date.now();
      setLastSeen(now);
      try {
        localStorage.setItem(SEEN_KEY, String(now));
      } catch {
        // localStorage unavailable — fine, just won't persist across reloads
      }
    }
  };

  return (
    <div className="icon-btn-wrapper" ref={wrapperRef}>
      <button
        className="icon-btn"
        aria-label="Notifications"
        title="Notifications"
        onClick={handleToggle}
      >
        <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
          <path
            d="M3 6.2C3 4 4.9 2.2 7.5 2.2S12 4 12 6.2V9L13 11H2L3 9V6.2Z"
            stroke="currentColor"
            strokeWidth="1.2"
            strokeLinejoin="round"
          />
          <path
            d="M6 12.5C6 13.3 6.7 14 7.5 14C8.3 14 9 13.3 9 12.5"
            stroke="currentColor"
            strokeWidth="1.2"
          />
        </svg>
        {unseenCount > 0 && (
          <span className="notification-badge">
            {unseenCount > 9 ? "9+" : unseenCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="notification-dropdown">
          <div className="notification-header">Opened &amp; closed positions</div>
          {positionEvents.length === 0 ? (
            <div className="notification-empty">No position activity yet.</div>
          ) : (
            positionEvents.map((entry) => {
              const isClosed = entry.status === "closed";
              const pnl = pnlText(entry);
              const stats = statsLine(entry);
              return (
                <div className="notification-item" key={entry.id}>
                  <div className="notification-item-title">
                    <span>
                      {cleanSymbol(entry.symbol)} —{" "}
                      {isClosed
                        ? "Position closed"
                        : entry.action === "buy"
                        ? "Long opened"
                        : "Short opened"}
                    </span>
                    <span
                      className="event-tag"
                      style={
                        isClosed
                          ? { color: "var(--down)", borderColor: "var(--down)" }
                          : undefined
                      }
                    >
                      {isClosed ? "Closed" : "Opened"}
                    </span>
                  </div>
                  {(stats || pnl !== null) && (
                    <div className="notification-item-stats">
                      {stats}
                      {pnl !== null && (
                        <span
                          style={{
                            color: pnl
                              ? Number(pnl) >= 0
                                ? "var(--up)"
                                : "var(--down)"
                              : undefined,
                          }}
                        >
                          {stats ? " · " : ""}
                          {pnl ? `PnL ${Number(pnl) >= 0 ? "+" : ""}$${pnl}` : "PnL —"}
                        </span>
                      )}
                    </div>
                  )}
                  <div className="notification-item-time">
                    {timeAgo(eventTimestampOf(entry) ?? "")}
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}