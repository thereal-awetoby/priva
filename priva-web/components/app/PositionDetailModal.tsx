"use client";

import { cleanSymbol } from "@/lib/format";

type Position = Record<string, any>;

export default function PositionDetailModal({
  position,
  onClose,
}: {
  position: Position;
  onClose: () => void;
}) {
  const opened =
    position.opened_at ?? position.timestamp ?? position.entry_time ?? null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose} aria-label="Close">
          Close ✕
        </button>

        <h2 className="modal-title">
          {cleanSymbol(position.symbol)}{" "}
          <span
            className={position.side === "buy" ? "up" : "down"}
            style={{ fontSize: "16px" }}
          >
            {position.side === "buy" ? "Long" : "Short"}
          </span>
        </h2>
        <p className="modal-sub">Live position detail from your paper account.</p>

        <div className="position-detail-grid">
          <div className="position-detail-item">
            <div className="position-detail-label">Open price</div>
            <div className="position-detail-value">
              ${Number(position.entry_price ?? 0).toFixed(2)}
            </div>
          </div>
          <div className="position-detail-item">
            <div className="position-detail-label">Current price</div>
            <div className="position-detail-value">
              ${Number(position.mark_price ?? 0).toFixed(2)}
            </div>
          </div>
          <div className="position-detail-item">
            <div className="position-detail-label">Position size</div>
            <div className="position-detail-value">
              {position.qty} (${Number(position.notional_usd ?? 0).toFixed(2)})
            </div>
          </div>
          <div className="position-detail-item">
            <div className="position-detail-label">Leverage</div>
            <div className="position-detail-value">{position.leverage}x</div>
          </div>
          <div className="position-detail-item">
            <div className="position-detail-label">Unrealized P&amp;L</div>
            <div
              className="position-detail-value"
              style={{ color: position.unrealized_pnl >= 0 ? "var(--up)" : "var(--down)" }}
            >
              {position.unrealized_pnl >= 0 ? "+" : ""}${Number(position.unrealized_pnl ?? 0).toFixed(2)}
            </div>
          </div>
          <div className="position-detail-item">
            <div className="position-detail-label">Opened</div>
            <div className="position-detail-value" style={{ fontSize: "12px" }}>
              {opened ? new Date(opened).toLocaleString() : "Not available yet"}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}