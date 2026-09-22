"use client";

import { useState, useEffect } from "react";
import { apiGet, apiPost } from "@/lib/api";

type Strategy = Record<string, any>;

const SUPPORTED_SYMBOLS = ["AAPLUSDT", "TSLAUSDT"];

export default function StrategyList({ typeFilter }: { typeFilter: string | null }) {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [symbols, setSymbols] = useState<string[]>(["AAPLUSDT"]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activating, setActivating] = useState(false);
  const [activateResult, setActivateResult] = useState<string | null>(null);

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

  const selected = strategies.find((s) => s.id === selectedId);
  const isPairs = selected?.type === "pairs_trading";

  useEffect(() => {
    if (selected?.type === "pairs_trading") {
      setSymbols(SUPPORTED_SYMBOLS);
    }
  }, [selectedId]);

  const toggleSymbol = (s: string) => {
    setSymbols((prev) =>
      prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]
    );
  };

  const handleActivate = async () => {
    if (!selectedId) return;
    setActivating(true);
    setActivateResult(null);
    try {
      const data = await apiPost<any>(`/strategies/${selectedId}/activate`, { symbols });
      console.log("ACTIVATE RESPONSE:", data);
      setActivateResult(
        `Activated on ${symbols.map((s) => s.replace("USDT", "")).join(", ")}.`
      );
    } catch (err: any) {
      setActivateResult(`Couldn't activate: ${err.message}`);
    } finally {
      setActivating(false);
    }
  };

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

  return (
    <div className="lab-grid">
      <div className="strategy-list">
        {strategies.map((s) => (
          <div
            key={s.id}
            className={`strategy-row ${selectedId === s.id ? "active" : ""}`}
            onClick={() => {
              setSelectedId(s.id);
              setActivateResult(null);
            }}
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

            <div className="form-field">
              <label className="form-label">Symbols</label>
              <div className="symbol-select">
                {SUPPORTED_SYMBOLS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    className={`symbol-chip ${symbols.includes(s) ? "active" : ""}`}
                    onClick={() => !isPairs && toggleSymbol(s)}
                    disabled={isPairs}
                  >
                    {s.replace("USDT", "")}
                  </button>
                ))}
              </div>
              {isPairs && (
                <div className="form-hint">Pairs trading requires both symbols.</div>
              )}
            </div>

            <button
              className="btn btn-primary"
              onClick={handleActivate}
              disabled={activating || symbols.length === 0}
              style={{ width: "100%", textAlign: "center", display: "block" }}
            >
              {activating
                ? "Activating…"
                : selected.status === "active"
                  ? "Apply symbols"
                  : "Activate strategy"}
            </button>

            {activateResult && (
              <div className="form-hint" style={{ marginTop: "12px" }}>
                {activateResult}
              </div>
            )}
          </div>
        ) : (
          <p className="panel-lead">Select a strategy to see details.</p>
        )}
      </div>
    </div>
  );
}