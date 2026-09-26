"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { apiGet } from "@/lib/api";
import Sidebar from "@/components/app/Sidebar";
import ControlCenterPanel from "@/components/app/panels/ControlCenterPanel";
import StrategyLabPanel from "@/components/app/panels/StrategyLabPanel";
import RiskAccessPanel from "@/components/app/panels/RiskAccessPanel";
import ActivityPanel from "@/components/app/panels/ActivityPanel";
import NotificationBell from "@/components/app/NotificationBell";
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
  const [workerStatus, setWorkerStatus] = useState<{ running?: boolean; workerError?: string; persistenceError?: string; error?: string } | null>(null);
  const router = useRouter();

  useEffect(() => {
    if (!hasSeenOnboarding()) {
            setShowOnboarding(true);
    }

    Promise.all([
      apiGet<{ user_id?: string; email?: string }>("/auth/session"),
      apiGet<{ running?: boolean; last_error?: string | null; last_persistence_status?: string | null; supabase_logging_configured?: boolean }>("/user/agent-loop"),
    ])
      .then(([, worker]) => {
        setWorkerStatus({ running: worker.running, workerError: worker.last_error ?? undefined, persistenceError: worker.last_persistence_status ?? (worker.supabase_logging_configured === false ? "Supabase logging not configured" : undefined) });
      })
      .catch((error) => {
        setWorkerStatus({ error: error instanceof Error ? error.message : "Unable to verify session" });
      });
  }, []);

  let workerState: "loading" | "live" | "stopped" | "error";
  let workerLabel: string;
  let workerTitle = "Background agent status";
  if (!workerStatus) {
    workerState = "loading";
    workerLabel = "Checking worker…";
  } else if (workerStatus.error) {
    workerState = "error";
    workerLabel = "Auth error";
    workerTitle = workerStatus.error;
  } else if (workerStatus.workerError) {
    workerState = "error";
    workerLabel = "Worker error";
    workerTitle = workerStatus.workerError;
  } else if (workerStatus.persistenceError === "error") {
    workerState = "error";
    workerLabel = "Logging error";
    workerTitle = "Cycle logging is failing — trading continues";
  } else if (workerStatus.running) {
    workerState = "live";
    workerLabel = "Worker running";
  } else {
    workerState = "stopped";
    workerLabel = "Worker stopped";
  }

  return (
    <div className="app-root">
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />

      <div className="app-main">
        <div className="app-topbar">
          <div className="app-crumb">
            Priva / <span>{crumbLabels[activeTab]}</span>
          </div>
          <div className="topbar-right">
            <div className="env-tag">Paper trading only · Withdrawals disabled</div>
            <div className={`worker-status worker-status-${workerState}`} title={workerTitle}>
              <span className="worker-status-dot" aria-hidden="true" />
              {workerLabel}
            </div>
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
            <NotificationBell />
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