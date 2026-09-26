"use client";

import { useRef, useState } from "react";
import { toPng } from "html-to-image";
import { cleanSymbol } from "@/lib/format";

type Position = Record<string, any>;

export default function PositionDetailModal({
  position,
  onClose,
}: {
  position: Position;
  onClose: () => void;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const formatTimestamp = (value: unknown) => {
    if (!value) return "—";
    const date = new Date(String(value));
    return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
  };
  const opened = position.opened_at ?? null;
  const closed = position.closed_at ?? null;
  const openedDate = opened ? new Date(String(opened)) : null;
  const closedDate = closed ? new Date(String(closed)) : null;
  const duration =
    openedDate && closedDate && !Number.isNaN(openedDate.getTime()) && !Number.isNaN(closedDate.getTime())
      ? Math.max(0, closedDate.getTime() - openedDate.getTime())
      : null;
  const durationLabel = duration == null
    ? "—"
    : `${Math.floor(duration / 3600000)}h ${Math.floor((duration % 3600000) / 60000)}m`;

  const handleDownload = async () => {
    if (!panelRef.current || isDownloading) return;
    setIsDownloading(true);
    setDownloadError(null);
    try {
      // filter excludes the Close/Download controls themselves from the
      // snapshot — only the card content gets captured.
      const dataUrl = await toPng(panelRef.current, {
        backgroundColor: getComputedStyle(document.documentElement).getPropertyValue("--bg-raised").trim() || "#172923",
        filter: (node) => !(node instanceof HTMLElement && node.dataset.noCapture === "true"),
        pixelRatio: 2,
      });
      const link = document.createElement("a");
      const symbolLabel = cleanSymbol(position.symbol) || "position";
      const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
      link.download = `priva-${symbolLabel.toLowerCase()}-${position.side ?? "position"}-${stamp}.png`;
      link.href = dataUrl;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (err: any) {
      setDownloadError(err?.message ?? "Couldn't generate the image");
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()} ref={panelRef}>
        <button className="modal-close" onClick={onClose} aria-label="Close" data-no-capture="true">
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

        {downloadError ? (
          <p className="modal-sub" style={{ color: "var(--down)" }} data-no-capture="true">
            {downloadError}
          </p>
        ) : null}

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
              {formatTimestamp(opened)}
            </div>
          </div>
          {closed && (
            <div className="position-detail-item">
              <div className="position-detail-label">Closed</div>
              <div className="position-detail-value" style={{ fontSize: "12px" }}>
                {formatTimestamp(closed)}
              </div>
            </div>
          )}
          {closed && (
            <div className="position-detail-item">
              <div className="position-detail-label">Duration</div>
              <div className="position-detail-value">{durationLabel}</div>
            </div>
          )}
        </div>

        <div className="modal-download-row" data-no-capture="true">
          <button
            className="modal-download"
            onClick={handleDownload}
            disabled={isDownloading}
            type="button"
          >
            {isDownloading ? "Saving…" : "Download PNG"}
          </button>
        </div>
      </div>
    </div>
  );
}