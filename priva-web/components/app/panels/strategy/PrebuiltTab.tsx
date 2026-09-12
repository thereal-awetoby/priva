"use client";

import { useState, useEffect } from "react";
import { apiGet } from "@/lib/api";

type Strategy = Record<string, any>;

export default function PrebuiltTab() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<Strategy[]>("/strategies")
      .then((data) => {
        console.log("STRATEGIES RESPONSE:", data);
        setStrategies(data);
        if (data.length > 0) {
          setSelectedId(data[0].id ?? data[0].strategy_id ?? null);
        }
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return <p className="panel-lead">Loading strategies…</p>;
  }

  if (error) {
    return (
      <div className="strategy-empty">
        Couldn&apos;t reach the strategy catalog ({error}). This clears up
        once the backend allows requests from this app.
      </div>
    );
  }

  const selected = strategies.find(
    (s) => (s.id ?? s.strategy_id) === selectedId
  );

  return (
    <div className="lab-grid">
      <div className="strategy-list">
        {strategies.map((s) => {
          const id = s.id ?? s.strategy_id;
          return (
            <div
              key={id}
              className={`strategy-row ${selectedId === id ? "active" : ""}`}
              onClick={() => setSelectedId(id)}
            >
              <div className="strategy-info">
                <h3>{s.name ?? "Untitled strategy"}</h3>
                <p>{s.description ?? ""}</p>
              </div>
              <div className="strategy-meta">
                <div className="strategy-meta-label">Risk profile</div>
                <div className="strategy-meta-value">
                  {s.risk_profile ?? s.riskProfile ?? "—"}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="config-panel">
        {selected ? (
          <div>
            <div className="config-head">
              <h3 className="config-title">{selected.name}</h3>
            </div>
            <p className="config-desc">
              {selected.long_description ?? selected.description ?? ""}
            </p>
            
            <a  className="btn btn-primary"
              href="#"
              style={{ width: "100%", textAlign: "center", display: "block" }}
            >
              Activate strategy
            </a>
          </div>
        ) : (
          <p className="panel-lead">Select a strategy to see details.</p>
        )}
      </div>
    </div>
  );
}