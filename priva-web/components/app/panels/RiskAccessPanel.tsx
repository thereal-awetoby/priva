"use client";

import { useState } from "react";

type Permission = {
  id: string;
  title: string;
  description: string;
  icon: React.ReactNode;
};

const permissions: Permission[] = [
  {
    id: "leverage-guard",
    title: "Leverage guard",
    description: "Never exceed your 2.0x ceiling.",
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
        <path d="M1.5 5L7.5 2L13.5 5L7.5 8L1.5 5Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
        <path d="M1.5 9.5L7.5 12.5L13.5 9.5M1.5 7.2L7.5 10.2L13.5 7.2" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    id: "drawdown-brake",
    title: "Drawdown brake",
    description: "Pause at 8% rolling drawdown.",
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
        <path d="M1.5 4L5 9L8 6.5L13.5 12" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    id: "earnings-blackout",
    title: "Earnings blackout",
    description: "No new positions 24h before earnings.",
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
        <circle cx="7.5" cy="7.5" r="5.7" stroke="currentColor" strokeWidth="1.2" />
        <path d="M7.5 4.5V7.5L9.7 9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "private-routing",
    title: "Private routing",
    description: "Route all execution through private relay.",
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
        <circle cx="7.5" cy="7.5" r="2" stroke="currentColor" strokeWidth="1.2" />
        <circle cx="7.5" cy="7.5" r="5.5" stroke="currentColor" strokeWidth="1.2" />
      </svg>
    ),
  },
];

export default function RiskAccessPanel() {
  const [toggles, setToggles] = useState<Record<string, boolean>>({
    "leverage-guard": true,
    "drawdown-brake": true,
    "earnings-blackout": true,
    "private-routing": true,
  });

  const toggle = (id: string) =>
    setToggles((prev) => ({ ...prev, [id]: !prev[id] }));

  return (
    <div>
      <div className="panel-eyebrow">Boundaries &amp; permissions</div>
      <h2 className="panel-heading">The guardrails are yours.</h2>
      <p className="panel-lead">
        Autonomy is only useful when the edges are explicit. These limits
        are evaluated before every decision.
      </p>

      <div className="risk-grid">
        <div className="permission-card">
          <div className="permission-card-head">
            <h3>Execution permissions</h3>
          </div>
          <p>A quiet check before every order.</p>

          {permissions.map((p) => (
            <div className="permission-row" key={p.id}>
              <div className="permission-icon">{p.icon}</div>
              <div className="permission-info">
                <h4>{p.title}</h4>
                <p>{p.description}</p>
              </div>
              <div
                className={`toggle ${toggles[p.id] ? "on" : ""}`}
                onClick={() => toggle(p.id)}
                role="switch"
                aria-checked={toggles[p.id]}
                tabIndex={0}
              >
                <div className="toggle-thumb" />
              </div>
            </div>
          ))}
        </div>

        <div className="scope-card">
          <div className="panel-title" style={{ marginBottom: "16px" }}>
            Permission scope
          </div>
          <div className="scope-badge">
            <div className="scope-badge-icon">
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <path d="M9 2.2L14 4V7.6C14 11 11.8 13 9 13.8C6.2 13 4 11 4 7.6V4L9 2.2Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
                <path d="M6.5 8L8.2 9.7L11.5 6.2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <div>
              <h4>Bounded</h4>
              <p>{Object.values(toggles).filter(Boolean).length} of 4 protections active</p>
            </div>
          </div>
          <ul className="scope-checks">
            <li>Trade only</li>
            <li>No withdrawals</li>
            <li>No transfers</li>
            <li>Manual kill switch</li>
          </ul>
          <div className="scope-note">Priva asks for less, so you can see more.</div>
        </div>
      </div>

      <div className="limits-block">
        <h3>Position limits</h3>
        <div className="limit-row">
          <div className="limit-label-row">
            <span>Portfolio exposure</span>
            <span className="limit-value">73% / 85%</span>
          </div>
          <div className="limit-track">
            <div className="limit-fill" style={{ width: "73%" }} />
          </div>
          <div className="limit-marks">
            <span>0%</span>
            <span>hard cap</span>
          </div>
        </div>
        <div className="limit-row">
                  <div className="limit-label-row">
                    <span>Max single position</span>
                    <span className="limit-value">18% / 25%</span>
                  </div>
                  <div className="limit-track">
                    <div className="limit-fill" style={{ width: "72%" }} />
                  </div>
                  <div className="limit-marks">
                    <span>0%</span>
                    <span>hard cap</span>
                  </div>
                </div>
      </div>
    </div>
  );
}