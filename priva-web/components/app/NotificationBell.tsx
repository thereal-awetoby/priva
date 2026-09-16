"use client";

import { useState, useEffect, useRef } from "react";
import { apiGet } from "@/lib/api";
import { timeAgo, cleanSymbol } from "@/lib/format";

type EventItem = Record<string, any>;

const SEEN_KEY = "priva_notifications_last_seen";

function isPositionOpened(entry: EventItem): boolean {
  const isTrade = entry.action === "buy" || entry.action === "sell";
  const wasBlocked = entry.risk_check?.allowed === false;
  const wasSkipped = entry.status === "skipped_existing_position";
  return isTrade && !wasBlocked && !wasSkipped;
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

  const openedPositions = entries.filter(isPositionOpened).slice(0, 20);

  const unseenCount = openedPositions.filter(
    (e) => e.timestamp && new Date(e.timestamp).getTime() > lastSeen
  ).length;

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
          <div className="notification-header">Positions opened</div>
          {openedPositions.length === 0 ? (
            <div className="notification-empty">No positions opened yet.</div>
          ) : (
            openedPositions.map((entry) => (
              <div className="notification-item" key={entry.id}>
                <div className="notification-item-title">
                  {cleanSymbol(entry.symbol)} —{" "}
                  {entry.action === "buy" ? "Long opened" : "Short opened"}
                </div>
                <div className="notification-item-time">
                  {timeAgo(entry.timestamp)}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}