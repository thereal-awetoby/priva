"use client";

import TradingLimitsForm from "@/components/app/panels/risk/TradingLimitsForm";

export default function RiskAccessPanel() {
  return (
    <div>
      <div className="panel-eyebrow">Boundaries &amp; permissions</div>
      <h2 className="panel-heading">The guardrails are yours.</h2>
      <p className="panel-lead">
        Autonomy is only useful when the edges are explicit. These limits
        are evaluated before every decision.
      </p>

      <div className="risk-grid">
              <TradingLimitsForm />

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
                    <p>4 of 4 protections active</p>
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
          </div>
        );
      }