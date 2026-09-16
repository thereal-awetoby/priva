"use client";

import { useEffect, useState } from "react";

type StrategyCatalogItem = {
  id: string;
  name: string;
  type: string;
  description: string;
  status: string;
};

const supportedSymbols = ["AAPLUSDT", "TSLAUSDT"];

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8001";

const strategyGlyphs: Record<string, string> = {
  prebuilt: "P",
  structured: "C",
  playbook: "B",
};

export default function StrategyLabPanel() {
  const [strategies, setStrategies] = useState<StrategyCatalogItem[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activating, setActivating] = useState(false);
  const [selectedSymbols, setSelectedSymbols] = useState<string[]>(supportedSymbols);
  const [strategyBySymbol, setStrategyBySymbol] = useState<Record<string, string>>({});

  const loadStrategies = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${API_BASE}/strategies`);
      if (!response.ok) {
        throw new Error(`Unable to load strategies (${response.status})`);
      }

      const payload = (await response.json()) as { strategies?: StrategyCatalogItem[] };
      const nextStrategies = payload.strategies ?? [];

      setStrategies(nextStrategies);
      if (nextStrategies.length > 0) {
        setSelectedId((current) => current || nextStrategies[0].id);
        setStrategyBySymbol((current) =>
          Object.fromEntries(supportedSymbols.map((symbol) => [symbol, current[symbol] ?? nextStrategies[0].id])),
        );
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load strategies");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStrategies();
  }, []);

  const selected = strategies.find((strategy) => strategy.id === selectedId) ?? null;

  const handleActivate = async () => {
    if (!selected) {
      return;
    }

    try {
      setActivating(true);
      setError(null);

      const response = await fetch(`${API_BASE}/strategies/${selected.id}/activate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbols: selectedSymbols, strategy_by_symbol: strategyBySymbol }),
      });

      const payload = (await response.json()) as { status?: string; message?: string };

      if (!response.ok || payload.status !== "activated") {
        throw new Error(payload.message ?? `Activation failed (${response.status})`);
      }

      setStrategies((current) =>
        current.map((strategy) => ({
          ...strategy,
          status: strategy.id === selected.id ? "active" : "inactive",
        })),
      );
    } catch (activateError) {
      setError(activateError instanceof Error ? activateError.message : "Unable to activate strategy");
    } finally {
      setActivating(false);
    }
  };

  return (
    <div>
      <div className="panel-eyebrow">Decision engine</div>
      <h2 className="panel-heading">Build the way Priva thinks.</h2>
      <p className="panel-lead">
        Choose a bounded strategy or shape your own. Every rule is visible
        before it can act.
      </p>

      {loading ? (
        <div className="config-panel">
          <p className="panel-lead">Loading strategy catalog…</p>
        </div>
      ) : error ? (
        <div className="config-panel">
          <p className="config-desc">{error}</p>
          <button className="btn btn-primary" onClick={loadStrategies} style={{ marginTop: 12 }}>
            Retry
          </button>
        </div>
      ) : (
        <div className="lab-grid">
          <div className="strategy-list">
            {strategies.map((strategy) => (
              <div
                key={strategy.id}
                className={`strategy-row ${selectedId === strategy.id ? "active" : ""}`}
                onClick={() => {
                  setSelectedId(strategy.id);
                  setStrategyBySymbol((current) => ({
                    ...current,
                    ...Object.fromEntries(selectedSymbols.map((symbol) => [symbol, strategy.id])),
                  }));
                }}
              >
                <div className="strategy-icon">{strategyGlyphs[strategy.type] ?? "S"}</div>
                <div className="strategy-info">
                  <h3>{strategy.name}</h3>
                  <p>{strategy.description}</p>
                </div>
                <div className="strategy-meta">
                  <div className="strategy-meta-label">Type</div>
                  <div className="strategy-meta-value">{strategy.type}</div>
                </div>
              </div>
            ))}
          </div>

          {selected ? (
            <div className="config-panel">
              <div className="config-head">
                <h3 className="config-title">{selected.name}</h3>
              </div>

              <p className="config-desc">{selected.description}</p>

              <div className="config-rows">
                <div className="config-row">
                  <span className="config-key">Strategy ID</span>
                  <span className="config-value">{selected.id}</span>
                </div>
                <div className="config-row">
                  <span className="config-key">Type</span>
                  <span className="config-value">{selected.type}</span>
                </div>
                <div className="config-row">
                  <span className="config-key">Status</span>
                  <span className="config-value">{selected.status}</span>
                </div>
              </div>

              <div className="config-row" style={{ display: "block" }}>
                <span className="config-key">Trade symbols</span>
                <div style={{ display: "flex", gap: 16, marginTop: 8 }}>
                  {supportedSymbols.map((symbol) => (
                    <label key={symbol} style={{ display: "flex", gap: 6, alignItems: "center" }}>
                      <input
                        type="checkbox"
                        checked={selectedSymbols.includes(symbol)}
                        onChange={() =>
                          setSelectedSymbols((current) =>
                            current.includes(symbol)
                              ? current.filter((currentSymbol) => currentSymbol !== symbol)
                              : [...current, symbol],
                          )
                        }
                      />
                      {symbol.replace("USDT", "")}
                    </label>
                  ))}
                </div>
              </div>

              {selectedSymbols.map((symbol) => (
                <label key={`${symbol}-strategy`} className="config-row">
                  <span className="config-key">{symbol.replace("USDT", "")} strategy</span>
                  <select
                    className="activity-search"
                    value={strategyBySymbol[symbol] ?? selected.id}
                    onChange={(event) => setStrategyBySymbol((current) => ({ ...current, [symbol]: event.target.value }))}
                  >
                    {strategies.map((strategy) => <option key={strategy.id} value={strategy.id}>{strategy.name}</option>)}
                  </select>
                </label>
              ))}

              <button
                className="btn btn-primary"
                onClick={handleActivate}
                disabled={activating || selectedSymbols.length === 0}
                style={{ width: "100%", textAlign: "center", display: "block" }}
              >
                {activating ? "Activating…" : selected.status === "active" ? "Apply symbols" : "Activate strategy"}
              </button>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}