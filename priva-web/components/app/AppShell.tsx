"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { apiGet, apiPost } from "@/lib/api";
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
  const [authDebug, setAuthDebug] = useState<{ userId?: string; email?: string; running?: boolean; workerError?: string; error?: string } | null>(null);
  const [backfillStatus, setBackfillStatus] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    if (!hasSeenOnboarding()) {
      setShowOnboarding(true);
    }

    Promise.all([
      apiGet<{ user_id?: string; email?: string }>("/auth/session"),
      apiGet<{ running?: boolean; last_error?: string | null; last_persistence_status?: string | null; supabase_logging_configured?: boolean }>("/user/agent-loop"),
    ])
      .then(([session, worker]) => {
        setAuthDebug({ userId: session.user_id, email: session.email, running: worker.running, workerError: worker.last_error ?? worker.last_persistence_status ?? (worker.supabase_logging_configured === false ? "Supabase logging not configured" : undefined) });
      })
      .catch((error) => {
        setAuthDebug({ error: error instanceof Error ? error.message : "Unable to verify session" });
      });
  }, []);

  const importTradeHistory = async () => {
    setBackfillStatus("Importing...");
    try {
      const result = await apiPost<{ imported?: number; skipped?: number; message?: string }>(
        "/user/backfill-trades",
        {
          start_time: Date.parse("2026-09-17T00:00:00Z"),
          end_time: Date.now(),
        },
      );
      setBackfillStatus(`${result.imported ?? 0} imported, ${result.skipped ?? 0} skipped`);
    } catch (error) {
      setBackfillStatus(error instanceof Error ? error.message : "Import failed");
    }
  };

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
            <div className="auth-debug" title="Temporary authentication diagnostics">
              {authDebug?.error ? (
                <span className="auth-debug-error">Auth error</span>
              ) : authDebug ? (
                <>
                  <span>{authDebug.email ?? authDebug.userId}</span>
                  <span className={authDebug.workerError ? "auth-debug-error" : authDebug.running ? "auth-debug-live" : "auth-debug-stopped"}>
                    {authDebug.workerError ? "worker error" : `worker ${authDebug.running ? "running" : "stopped"}`}
                  </span>
                </>
              ) : (
                <span>Checking auth...</span>
              )}
            </div>
            <button className="sign-out-btn" type="button" onClick={importTradeHistory}>
              Import history
            </button>
            {backfillStatus ? <span className="backfill-status">{backfillStatus}</span> : null}
            <button
              className="sign-out-btn"
              type="button"
              onClick={async () => {
                await createClient().auth.signOut();
                router.replace("/");
              }}
            >
              Sign out
            </button>
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