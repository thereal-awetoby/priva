"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { apiGet } from "@/lib/api";
import type { Session, AuthChangeEvent } from "@supabase/supabase-js";
import Sidebar from "@/components/app/Sidebar";
import AccountConnectScreen from "@/components/app/AccountConnectScreen";
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

type AccountState = "checking" | "connected" | "not_configured" | "unavailable";

function clearUserScopedStorage(userId: string) {
  const userKeys = [
    `priva_notifications_last_seen:${userId}`,
    `priva_onboarding_complete:${userId}`,
    `priva_workspace_name:${userId}`,
    "priva_notifications_last_seen",
    "priva_onboarding_complete",
  ];
  for (const key of userKeys) {
    try {
      localStorage.removeItem(key);
      sessionStorage.removeItem(key);
    } catch {
      // Storage can be unavailable in restricted browser contexts.
    }
  }
}

export default function AppShell() {
  const [activeTab, setActiveTab] = useState("control");
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [showSignOutConfirm, setShowSignOutConfirm] = useState(false);
  const [signOutLoading, setSignOutLoading] = useState(false);
  const [accountState, setAccountState] = useState<AccountState>("checking");
  const [userId, setUserId] = useState<string | null>(null);
  const [email, setEmail] = useState<string | undefined>();
  const [workerStatus, setWorkerStatus] = useState<{ running?: boolean; workerError?: string; persistenceError?: string; error?: string } | null>(null);
  const router = useRouter();

  useEffect(() => {
    let active = true;
    let authRevision = 0;
    let previousUserId: string | null = null;
    let sessionInitialized = false;
    let sessionEventReceived = false;
    const supabase = createClient();

    const applySession = (session: Session | null) => {
      const currentUser = session?.user ?? null;
      const currentUserId = currentUser?.id ?? null;
      if (sessionInitialized && currentUserId === previousUserId) {
        setEmail(currentUser?.email);
        return;
      }
      sessionInitialized = true;
      const revision = ++authRevision;
      if (previousUserId && previousUserId !== currentUserId) {
        clearUserScopedStorage(previousUserId);
      }
      previousUserId = currentUserId;
      setUserId(currentUserId);
      setEmail(currentUser?.email);
      setWorkerStatus(null);
      if (!session) {
        setAccountState("not_configured");
        window.location.replace("/?auth=login");
        return;
      }

      setAccountState("checking");
      apiGet<{ status?: string; connected?: boolean }>("/account/status")
        .then((status) => {
          if (!active || revision !== authRevision) return;
          setAccountState(status.connected || status.status === "connected" ? "connected" : "not_configured");
        })
        .catch(() => {
          if (active && revision === authRevision) setAccountState("unavailable");
        });
    };

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event: AuthChangeEvent, session: Session | null) => {
        sessionEventReceived = true;
        applySession(session);
      },
    );
    void supabase.auth.getSession().then((
      { data: { session } }: { data: { session: Session | null } },
    ) => {
      if (active && !sessionEventReceived) applySession(session);
    }).catch(() => {
      if (active && !sessionEventReceived) applySession(null);
    });

    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, []);

  useEffect(() => {
    if (accountState !== "connected" || !userId) {
      setWorkerStatus(null);
      setShowOnboarding(false);
      return;
    }
    if (!hasSeenOnboarding(userId)) setShowOnboarding(true);
    let active = true;
    apiGet<{ running?: boolean; last_error?: string | null; last_persistence_status?: string | null; supabase_logging_configured?: boolean }>("/user/agent-loop")
      .then((worker) => {
        if (!active) return;
        setWorkerStatus({
          running: worker.running,
          workerError: worker.last_error ?? undefined,
          persistenceError: worker.last_persistence_status ?? (worker.supabase_logging_configured === false ? "Supabase logging not configured" : undefined),
        });
      })
      .catch((error) => {
        if (active) setWorkerStatus({ error: error instanceof Error ? error.message : "Unable to verify agent status" });
      });
    return () => {
      active = false;
    };
  }, [accountState, userId]);

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

  const confirmSignOut = async () => {
    setSignOutLoading(true);
    try {
      if (userId) clearUserScopedStorage(userId);
      await createClient().auth.signOut();
      router.replace("/");
    } catch (err: any) {
      alert(`Couldn't sign out: ${err?.message ?? "unknown error"}`);
      setSignOutLoading(false);
    }
  };

  const retryAccountStatus = () => {
    setAccountState("checking");
    apiGet<{ status?: string; connected?: boolean }>("/account/status")
      .then((status) => setAccountState(status.connected || status.status === "connected" ? "connected" : "not_configured"))
      .catch(() => setAccountState("unavailable"));
  };

  if (accountState === "checking") {
    return <main className="auth-loading">Checking your Bitget demo account...</main>;
  }

  if (accountState !== "connected") {
    return (
      <AccountConnectScreen
        email={email}
        unavailable={accountState === "unavailable"}
        onRetry={retryAccountStatus}
        onSignOut={confirmSignOut}
        onConnected={() => setAccountState("connected")}
      />
    );
  }

  return (
    <div className="app-root">
      <Sidebar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onConnectionChange={(status) => setAccountState(status)}
      />

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
              onClick={() => setShowSignOutConfirm(true)}
            >
              Sign out
            </button>
            {userId ? <NotificationBell key={userId} userId={userId} /> : null}
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
        <OnboardingModal userId={userId ?? ""} onClose={() => setShowOnboarding(false)} />
      )}

      {showSignOutConfirm && (
        <div className="modal-overlay" onClick={() => !signOutLoading && setShowSignOutConfirm(false)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
            <button
              className="modal-close"
              onClick={() => setShowSignOutConfirm(false)}
              aria-label="Close"
              disabled={signOutLoading}
            >
              Close ✕
            </button>
            <h2 className="modal-title">Sign out?</h2>
            <p className="modal-sub">
              You&apos;ll be returned to the landing page and will need to sign back in to access your workspace.
            </p>
            <div className="connection-actions">
              <button
                className="btn"
                onClick={() => setShowSignOutConfirm(false)}
                disabled={signOutLoading}
              >
                Cancel
              </button>
              <button
                className="btn btn-danger"
                onClick={confirmSignOut}
                disabled={signOutLoading}
              >
                {signOutLoading ? "Signing out…" : "Sign out"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}