"use client";

import { useState, useEffect } from "react";
import { apiGet } from "@/lib/api";

type Strategy = Record<string, any>;

export default function StrategyList({ typeFilter }: { typeFilter: string | null }) {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<any>("/strategies")
      .then((data) => {
        const all: Strategy[] = Array.isArray(data)
          ? data
          : Array.isArray(data?.strategies)
            ? data.strategies
            : [];
        const filtered = typeFilter ? all.filter((s) => s.type === typeFilter) : all;
        setStrategies(filtered);
        if (filtered.length > 0) {
          setSelectedId(filtered[0].id ?? null);
        }
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [typeFilter]);

  if (loading) {
    return <p className="panel-lead">Loading strategies…</p>;
  }

  if (error) {
    return (
      <div className="strategy-empty">
        Couldn&apos;t reach the strategy catalog ({error}).
      </div>
    );
  }

  if (strategies.length === 0) {
    return (
        <div className="strategy-empty">
            No strategies available yet.
        </div>
    );
  }

  const selected = strategies.find((s) => s.id === selectedId);

  return (
    <div className="lab-grid">
      <div className="strategy-list">
        {strategies.map((s) => (
          <div
            key={s.id}
            className={`strategy-row ${selectedId === s.id ? "active" : ""}`}
            onClick={() => setSelectedId(s.id)}
          >
            <div className="strategy-info">
              <h3>{s.name ?? "Untitled strategy"}</h3>
              <p>{s.description ?? ""}</p>
            </div>
            <div className="strategy-meta">
              <div className="strategy-meta-label">Status</div>
              <div
                className="strategy-meta-value"
                style={{ color: s.status === "active" ? "var(--up)" : "var(--ink-faint)" }}
              >
                {s.status === "active" ? "Active" : "Inactive"}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="config-panel">
        {selected ? (
          <div>
            <div className="config-head">
              <h3 className="config-title">{selected.name}</h3>
            </div>
            <p className="config-desc">{selected.description ?? ""}</p>
            <a className="btn btn-primary" href="#" style={{ width: "100%", textAlign: "center", display: "block" }}>Activate strategy</a>
          </div>
        ) : (
          <p className="panel-lead">Select a strategy to see details.</p>
        )}
      </div>
    </div>
  );
}