"use client";

import { useState, useEffect } from "react";
import Sidebar from "@/components/app/Sidebar";
import ControlCenterPanel from "@/components/app/panels/ControlCenterPanel";
import StrategyLabPanel from "@/components/app/panels/StrategyLabPanel";
import RiskAccessPanel from "@/components/app/panels/RiskAccessPanel";
import ActivityPanel from "@/components/app/panels/ActivityPanel";
import OnboardingModal, { hasSeenOnboarding } from "@/components/app/OnboardingModal";

const crumbLabels: Record<string, string> = {
  control: "Control center",
  strategy: "Strategy lab",
  risk: "Risk & access",
  activity: "Activity",
};

export default function AppShell() {
  const [activeTab, setActiveTab] = useState("control");
  const [showOnboarding, setShowOnboarding] = useState(false);

  useEffect(() => {
    if (!hasSeenOnboarding()) {
      setShowOnboarding(true);
    }
  }, []);

  return (
    <div className="app-root">
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />

      <div className="app-main">
        <div className="app-topbar">
          <div className="app-crumb">
            Priva / <span>{crumbLabels[activeTab]}</span>
          </div>
          <div className="topbar-right">
            <div className="env-tag">Paper environment</div>
            <button className="icon-btn" aria-label="Notifications" title="Notifications">
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
            </button>
            <button className="icon-btn" aria-label="Settings" title="Settings">
              <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
                <circle cx="7.5" cy="7.5" r="2.3" stroke="currentColor" strokeWidth="1.2" />
                <path
                  d="M7.5 1.8V3.3M7.5 11.7V13.2M13.2 7.5H11.7M3.3 7.5H1.8M11.5 3.5L10.4 4.6M4.6 10.4L3.5 11.5M11.5 11.5L10.4 10.4M4.6 4.6L3.5 3.5"
                  stroke="currentColor"
                  strokeWidth="1.1"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          </div>
        </div>

        <div className="app-content">
          {activeTab === "control" && <ControlCenterPanel />}
          {activeTab === "strategy" && <StrategyLabPanel />}
          {activeTab === "risk" && <RiskAccessPanel />}
          {activeTab === "activity" && <ActivityPanel />}
        </div>
      </div>

      {showOnboarding && (
        <OnboardingModal onClose={() => setShowOnboarding(false)} />
      )}
    </div>
  );
}