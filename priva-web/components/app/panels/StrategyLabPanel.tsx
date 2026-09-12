"use client";

import { useState } from "react";

const strategies = [
  {
    id: "quiet-momentum",
    name: "Quiet Momentum",
    description: "Follows durable trend with a wide noise filter.",
    riskProfile: "Measured",
    longDescription: "A patient system for staying in the trade without chasing the move.",
    universe: "Tokenized U.S. equities",
    cadence: "Every 15 minutes",
    maxPosition: "15% of portfolio",
    leverage: "Up to 2.0x",
    icon: (
      <svg width="17" height="17" viewBox="0 0 17 17" fill="none">
        <path
          d="M2 13L6 8L9.5 10.5L15 4"
          stroke="currentColor"
          strokeWidth="1.3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
  {
    id: "range-keeper",
    name: "Range Keeper",
    description: "Mean reversion for high-liquidity sessions.",
    riskProfile: "Conservative",
    longDescription: "Buys dips and sells rips inside an established trading range.",
    universe: "Tokenized U.S. equities",
    cadence: "Every 5 minutes",
    maxPosition: "10% of portfolio",
    leverage: "Up to 1.5x",
    icon: (
      <svg width="17" height="17" viewBox="0 0 17 17" fill="none">
        <path d="M3 4V13M14 4V13" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
        <path d="M3 8.5H14" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "event-horizon",
    name: "Event Horizon",
    description: "Responds to structured earnings volatility.",
    riskProfile: "Selective",
    longDescription: "Positions ahead of scheduled catalysts within tightly bounded risk.",
    universe: "Tokenized U.S. equities",
    cadence: "Event-driven",
    maxPosition: "8% of portfolio",
    leverage: "Up to 1.2x",
    icon: (
      <svg width="17" height="17" viewBox="0 0 17 17" fill="none">
        <circle cx="8.5" cy="8.5" r="6" stroke="currentColor" strokeWidth="1.3" />
        <path
          d="M8.5 5V8.5L11 10.5"
          stroke="currentColor"
          strokeWidth="1.3"
          strokeLinecap="round"
        />
      </svg>
    ),
  },
];

export default function StrategyLabPanel() {
  const [selectedId, setSelectedId] = useState(strategies[0].id);
  const selected = strategies.find((s) => s.id === selectedId)!;

  return (
    <div>
      <div className="panel-eyebrow">Decision engine</div>
      <h2 className="panel-heading">Build the way Priva thinks.</h2>
      <p className="panel-lead">
        Choose a bounded strategy or shape your own. Every rule is visible
        before it can act.
      </p>

      <div className="lab-grid">
        <div className="strategy-list">
          {strategies.map((s) => (
            <div
              key={s.id}
              className={`strategy-row ${selectedId === s.id ? "active" : ""}`}
              onClick={() => setSelectedId(s.id)}
            >
              <div className="strategy-icon">{s.icon}</div>
              <div className="strategy-info">
                <h3>{s.name}</h3>
                <p>{s.description}</p>
              </div>
              <div className="strategy-meta">
                <div className="strategy-meta-label">Risk profile</div>
                <div className="strategy-meta-value">{s.riskProfile}</div>
              </div>
            </div>
          ))}
        </div>

        <div className="config-panel">
          <div className="config-head">
            <h3 className="config-title">{selected.name}</h3>
          </div>
          <p className="config-desc">{selected.longDescription}</p>

          <div className="config-rows">
            <div className="config-row">
              <span className="config-key">Universe</span>
              <span className="config-value">{selected.universe}</span>
            </div>
            <div className="config-row">
              <span className="config-key">Signal cadence</span>
              <span className="config-value">{selected.cadence}</span>
            </div>
            <div className="config-row">
              <span className="config-key">Max position</span>
              <span className="config-value">{selected.maxPosition}</span>
            </div>
            <div className="config-row">
              <span className="config-key">Leverage</span>
              <span className="config-value">{selected.leverage}</span>
            </div>
          </div>

          <a className="btn btn-primary" href="#" style={{ width: "100%", textAlign: "center", display: "block" }}>
            Activate strategy
          </a>
        </div>
      </div>
    </div>
  );
}