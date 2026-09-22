"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type SidebarProps = {
  activeTab: string;
  onTabChange: (tab: string) => void;
};

const WORKSPACE_NAME_KEY = "priva_workspace_name";

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

export default function Sidebar({ activeTab, onTabChange }: SidebarProps) {
  const [connection, setConnection] = useState<{ status?: string; position_mode?: string } | null>(null);
  const [isConnectOpen, setIsConnectOpen] = useState(false);
  const [isConfirmingDisconnect, setIsConfirmingDisconnect] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [credentials, setCredentials] = useState({ apiKey: "", apiSecret: "", passphrase: "" });
  const [workspaceName, setWorkspaceName] = useState("Unknown");
  const [isEditingName, setIsEditingName] = useState(false);
  const [nameInput, setNameInput] = useState("");

    useEffect(() => {
      apiGet<{ status?: string; position_mode?: string }>("/debug/bitget-account")
      .then((payload) => setConnection(payload))
      .catch(() => setConnection({ status: "unavailable" }));
  }, []);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(WORKSPACE_NAME_KEY);
      if (stored) setWorkspaceName(stored);
    } catch {
      // localStorage unavailable — name just stays "Unknown"
    }
  }, []);

  const connected = connection?.status === "ok";

  const handleConnect = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setConnecting(true);
    setConnectionError(null);
    try {
      const payload = await apiPost<{ status?: string; message?: string; position_mode?: string }>(
        "/connection/bitget",
        {
          api_key: credentials.apiKey,
          api_secret: credentials.apiSecret,
          passphrase: credentials.passphrase,
        },
      );
      if (payload.status !== "connected") {
        throw new Error(payload.message ?? "Bitget credentials could not be verified");
      }
      setConnection({ status: "ok", position_mode: payload.position_mode });
      setCredentials({ apiKey: "", apiSecret: "", passphrase: "" });
      setIsConnectOpen(false);
    } catch (error) {
      setConnectionError(error instanceof Error ? error.message : "Unable to connect Bitget");
    } finally {
      setConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    setDisconnecting(true);
    try {
      await apiPost("/connection/bitget/disconnect", {});
      setConnection({ status: "not_configured" });
      setIsConfirmingDisconnect(false);
      setIsConnectOpen(false);
    } finally {
      setDisconnecting(false);
    }
  };

  const saveName = () => {
    const trimmed = nameInput.trim();
    const finalName = trimmed === "" ? "Unknown" : trimmed;
    setWorkspaceName(finalName);
    setIsEditingName(false);
    try {
      localStorage.setItem(WORKSPACE_NAME_KEY, finalName);
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
                <div className="connection-name">Bitget paper</div>
                <div className="connection-sub">
                  {connected
                    ? `${connection?.position_mode ?? "configured"} mode`
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
                              if (e.key === "Escape") setIsEditingName(false);
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
                  Credentials are verified by the backend and held in memory
                  only. Withdrawal access is not used.
                </p>
                <form onSubmit={handleConnect}>
                  <div className="form-field">
                    <label className="form-label">API key</label>
                    <input
                      className="form-input"
                      type="text"
                      autoComplete="off"
                      required
                      value={credentials.apiKey}
                      onChange={(event) =>
                        setCredentials({ ...credentials, apiKey: event.target.value })
                      }
                    />
                  </div>
                  <div className="form-field">
                    <label className="form-label">API secret</label>
                    <input
                      className="form-input"
                      type="password"
                      autoComplete="off"
                      required
                      value={credentials.apiSecret}
                      onChange={(event) =>
                        setCredentials({ ...credentials, apiSecret: event.target.value })
                      }
                    />
                  </div>
                  <div className="form-field">
                    <label className="form-label">Passphrase</label>
                    <input
                      className="form-input"
                      type="password"
                      autoComplete="off"
                      required
                      value={credentials.passphrase}
                      onChange={(event) =>
                        setCredentials({ ...credentials, passphrase: event.target.value })
                      }
                    />
                  </div>
                  {connectionError ? (
                    <p className="form-hint" style={{ color: "var(--down)" }}>
                      {connectionError}
                    </p>
                  ) : null}
                  <div className="connection-actions">
                    <button className="btn btn-primary" type="submit" disabled={connecting}>
                      {connecting ? "Verifying…" : "Connect demo account"}
                    </button>
                    {connected ? (
                      <button
                        className="btn"
                        type="button"
                        onClick={() => setIsConfirmingDisconnect(true)}
                      >
                        Disconnect
                      </button>
                    ) : null}
                  </div>
                </form>
              </>
            )}
          </div>
        </div>
      ) : null}
    </>
  );
}