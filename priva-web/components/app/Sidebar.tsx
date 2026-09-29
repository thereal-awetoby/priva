"use client";

import { useEffect, useRef, useState } from "react";
import type { AuthChangeEvent, Session } from "@supabase/supabase-js";
import { apiDelete, apiGet } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import ConnectAccountForm from "@/components/app/ConnectAccountForm";

type SidebarProps = {
  activeTab: string;
  onTabChange: (tab: string) => void;
  onConnectionChange: (status: "connected" | "not_configured") => void;
};

const WORKSPACE_NAME_KEY = "priva_workspace_name";
const CONNECTION_CHECK_INTERVAL_MS = 15_000;
const CONNECTION_CHECK_TIMEOUT_MS = 10_000;

const navItems = [
  {
    id: "control",
    label: "Control center",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.3" />
        <path d="M8 8L10.2 5.6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "strategy",
    label: "Strategy lab",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <circle cx="8" cy="4" r="1.6" stroke="currentColor" strokeWidth="1.2" />
        <circle cx="4" cy="12" r="1.6" stroke="currentColor" strokeWidth="1.2" />
        <circle cx="12" cy="12" r="1.6" stroke="currentColor" strokeWidth="1.2" />
        <path d="M8 5.6V8M8 8L4 10.6M8 8L12 10.6" stroke="currentColor" strokeWidth="1.2" />
      </svg>
    ),
  },
  {
    id: "risk",
    label: "Risk & access",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path
          d="M8 2.2L13 4V7.6C13 11 10.8 13 8 13.8C5.2 13 3 11 3 7.6V4L8 2.2Z"
          stroke="currentColor"
          strokeWidth="1.2"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
  {
    id: "activity",
    label: "Activity",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path
          d="M2 8.5H5L6.3 5L9.2 11.5L10.5 8.5H14"
          stroke="currentColor"
          strokeWidth="1.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
];

export default function Sidebar({ activeTab, onTabChange, onConnectionChange }: SidebarProps) {
  const [connection, setConnection] = useState<{ status?: string; position_mode?: string } | null>(null);
  const [isConnectOpen, setIsConnectOpen] = useState(false);
  const [isConfirmingDisconnect, setIsConfirmingDisconnect] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [workspaceName, setWorkspaceName] = useState("Unknown");
  const [isEditingName, setIsEditingName] = useState(false);
  const [nameInput, setNameInput] = useState("");
  const connectionCheckVersionRef = useRef(0);
  const workspaceUserIdRef = useRef<string | null>(null);
  const editingWorkspaceUserIdRef = useRef<string | null>(null);

  useEffect(() => {
    let active = true;
    let pendingController: AbortController | null = null;

    const checkConnection = async () => {
      const checkVersion = ++connectionCheckVersionRef.current;
      const controller = new AbortController();
      pendingController = controller;
      const timeout = window.setTimeout(() => controller.abort(), CONNECTION_CHECK_TIMEOUT_MS);

      try {
        const payload = await apiGet<{ status?: string }>("/account/status", { signal: controller.signal });
        if (!active || checkVersion !== connectionCheckVersionRef.current) return;
        if (payload.status === "connected" || payload.status === "not_configured") {
          setConnection({ status: payload.status });
        } else {
          setConnection({ status: "unavailable" });
        }
      } catch {
        if (active && checkVersion === connectionCheckVersionRef.current) {
          setConnection({ status: "unavailable" });
        }
      } finally {
        window.clearTimeout(timeout);
        if (pendingController === controller) pendingController = null;
      }
    };

    void checkConnection();
    const interval = window.setInterval(() => void checkConnection(), CONNECTION_CHECK_INTERVAL_MS);
    return () => {
      active = false;
      connectionCheckVersionRef.current += 1;
      window.clearInterval(interval);
      pendingController?.abort();
    };
  }, []);

  useEffect(() => {
    let active = true;
    let authEventRevision = 0;

    const applySession = (session: Session | null, force = false) => {
      const user = session?.user ?? null;
      const userId = user?.id ?? null;
      if (!force && userId === workspaceUserIdRef.current) return;

      workspaceUserIdRef.current = userId;
      editingWorkspaceUserIdRef.current = null;
      setIsEditingName(false);
      setNameInput("");
      setWorkspaceName("Unknown");
      if (!user) return;

      const metadataName = [
        user.user_metadata?.full_name,
        user.user_metadata?.name,
        user.user_metadata?.display_name,
      ].find((value): value is string => typeof value === "string" && value.trim().length > 0)?.trim();
      const accountName = metadataName || user.email?.split("@")[0] || "Unknown";

      try {
        const savedName = localStorage.getItem(`${WORKSPACE_NAME_KEY}:${userId}`);
        setWorkspaceName(savedName?.trim() || accountName);
      } catch {
        setWorkspaceName(accountName);
      }
    };

    try {
      localStorage.removeItem(WORKSPACE_NAME_KEY);
    } catch {
      // localStorage unavailable — account metadata remains the fallback
    }

    const supabase = createClient();
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event: AuthChangeEvent, session: Session | null) => {
      authEventRevision += 1;
      applySession(session, event === "USER_UPDATED");
    });
    const initialAuthEventRevision = authEventRevision;

    void supabase.auth.getSession().then(({ data: { session } }: { data: { session: Session | null } }) => {
      if (active && authEventRevision === initialAuthEventRevision) applySession(session);
    }).catch(() => {
      if (active && authEventRevision === initialAuthEventRevision) applySession(null);
    });

    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, []);

  const connected = connection?.status === "connected";

  const handleDisconnect = async () => {
    setDisconnecting(true);
    try {
      await apiDelete("/account/disconnect");
      connectionCheckVersionRef.current += 1;
      setConnection({ status: "not_configured" });
      onConnectionChange("not_configured");
      setIsConfirmingDisconnect(false);
      setIsConnectOpen(false);
    } catch (error) {
      setConnectionError(error instanceof Error ? error.message : "Unable to disconnect Bitget");
    } finally {
      setDisconnecting(false);
    }
  };

  const saveName = () => {
    const userId = workspaceUserIdRef.current;
    const editingUserId = editingWorkspaceUserIdRef.current;
    editingWorkspaceUserIdRef.current = null;
    setIsEditingName(false);
    if (editingUserId !== userId) return;

    const trimmed = nameInput.trim();
    const finalName = trimmed === "" ? "Unknown" : trimmed;
    setWorkspaceName(finalName);
    try {
      if (userId) localStorage.setItem(`${WORKSPACE_NAME_KEY}:${userId}`, finalName);
    } catch {
      // localStorage unavailable — won't persist across reloads, that's fine
    }
  };

  const closeModal = () => {
    setIsConnectOpen(false);
    setIsConfirmingDisconnect(false);
    setConnectionError(null);
  };

  return (
    <>
      <aside className="app-sidebar">
        <div className="sidebar-top">
          <div className="wordmark">
            Pr<span>i</span>va
          </div>
          <div className="env-dot" title="System nominal" />
        </div>

        <div className="sidebar-section-label">Workspace</div>
        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${activeTab === item.id ? "active" : ""}`}
              onClick={() => onTabChange(item.id)}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <button
            className="connection-card"
            type="button"
            onClick={() => {
              setConnectionError(null);
              setIsConnectOpen(true);
            }}
          >
            <div className="connection-label">Connection</div>
            <div className="connection-row">
              <div className="connection-mark">B</div>
              <div>
                <div className="connection-name">{connected ? "Bitget demo" : "Connect account"}</div>
                <div className="connection-sub">
                  {connected
                    ? connection?.position_mode
                      ? `${connection.position_mode} mode`
                      : "Connected"
                    : connection?.status === "not_configured"
                      ? "Not configured"
                      : "Unavailable"}
                </div>
              </div>
              <div
                className="connection-dot"
                style={!connected ? { background: "var(--ink-faint)" } : {}}
              />
            </div>
          </button>
          <div className="profile-row">
                      <div className="profile-avatar">{workspaceName.charAt(0).toUpperCase()}</div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        {isEditingName ? (
                          <input
                            className="profile-name-input"
                            value={nameInput}
                            onChange={(e) => setNameInput(e.target.value)}
                            onBlur={saveName}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") saveName();
                              if (e.key === "Escape") {
                                editingWorkspaceUserIdRef.current = null;
                                setIsEditingName(false);
                              }
                            }}
                            autoFocus
                          />
                        ) : (
                          <div className="profile-name">{workspaceName}</div>
                        )}
                        <div className="profile-sub">Private workspace</div>
                      </div>
                      <button
                        className="profile-edit-btn"
                        type="button"
                        onClick={() => {
                          editingWorkspaceUserIdRef.current = workspaceUserIdRef.current;
                          setNameInput(workspaceName === "Unknown" ? "" : workspaceName);
                          setIsEditingName(true);
                        }}
                        aria-label="Edit workspace name"
                        title="Edit name"
                      >
                        <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                          <path d="M8.5 1.5L11.5 4.5L4 12H1V9L8.5 1.5Z" stroke="currentColor" strokeWidth="1.1" strokeLinejoin="round" />
                        </svg>
                      </button>
                    </div>
        </div>
      </aside>

      {isConnectOpen ? (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-panel" onClick={(event) => event.stopPropagation()}>
            <button
              className="modal-close"
              type="button"
              onClick={closeModal}
              aria-label="Close connection form"
            >
              Close ✕
            </button>

            {isConfirmingDisconnect ? (
              <>
                <h2 className="modal-title">Disconnect Bitget?</h2>
                <p className="modal-sub">
                  Priva will no longer be able to place trades until you
                  reconnect a demo account.
                </p>
                {connectionError ? <p className="account-connect-error" role="alert">{connectionError}</p> : null}
                <div className="connection-actions">
                  <button
                    className="btn"
                    type="button"
                    onClick={() => setIsConfirmingDisconnect(false)}
                  >
                    Cancel
                  </button>
                  <button
                    className="btn btn-danger"
                    type="button"
                    onClick={handleDisconnect}
                    disabled={disconnecting}
                  >
                    {disconnecting ? "Disconnecting…" : "Yes, disconnect"}
                  </button>
                </div>
              </>
            ) : (
              <>
                <h2 className="modal-title">Connect Bitget demo</h2>
                <p className="modal-sub">
                  Connect the paper account associated with your Bitget login.
                </p>
                <ConnectAccountForm
                  submitLabel={connected ? "Reconnect account" : "Connect demo account"}
                  onConnected={(positionMode) => {
                    connectionCheckVersionRef.current += 1;
                    setConnection({ status: "connected", position_mode: positionMode });
                    onConnectionChange("connected");
                    setIsConnectOpen(false);
                  }}
                />
                {connected ? (
                  <div className="connection-actions">
                    <button className="btn" type="button" onClick={() => setIsConfirmingDisconnect(true)}>
                      Disconnect
                    </button>
                  </div>
                ) : null}
              </>
            )}
          </div>
        </div>
      ) : null}
    </>
  );
}