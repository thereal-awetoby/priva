"use client";

import { useState } from "react";
import { createClient } from "@/lib/supabase/client";

type ConnectModalProps = {
  isOpen: boolean;
  onClose: () => void;
};

export default function ConnectModal({ isOpen, onClose }: ConnectModalProps) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const submitAuth = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setMessage(null);

    try {
      const supabase = createClient();
      const result =
        mode === "login"
          ? await supabase.auth.signInWithPassword({ email, password })
          : await supabase.auth.signUp({ email, password });

      if (result.error) throw result.error;

      if (mode === "signup" && !result.data.session) {
        setMessage("Check your email to confirm your account, then sign in.");
        setMode("login");
        return;
      }

      window.location.href = "/app";
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Authentication failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose} aria-label="Close">
          Close ✕
        </button>

        <h2 className="modal-title">{mode === "login" ? "Sign in to Priva" : "Create your Priva account"}</h2>
        <p className="modal-sub">
          {mode === "login"
            ? "Access your private paper-trading workspace."
            : "Create an account to keep your workspace and strategies private."}
        </p>

        <form onSubmit={submitAuth}>
          <div className="form-field">
            <label className="form-label" htmlFor="auth-email">Email</label>
            <input
              className="form-input"
              id="auth-email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <div className="form-field">
            <label className="form-label" htmlFor="auth-password">Password</label>
            <div className="password-field">
              <input
                className="form-input"
                id="auth-password"
                type={showPassword ? "text" : "password"}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                minLength={6}
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowPassword((current) => !current)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                aria-pressed={showPassword}
                tabIndex={-1}
              >
                {showPassword ? (
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path
                      d="M1.5 8S3.8 3 8 3s6.5 5 6.5 5-2.3 5-6.5 5-6.5-5-6.5-5Z"
                      stroke="currentColor"
                      strokeWidth="1.2"
                      strokeLinejoin="round"
                    />
                    <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.2" />
                  </svg>
                ) : (
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path
                      d="M1.5 8S3.8 3 8 3s6.5 5 6.5 5-2.3 5-6.5 5-6.5-5-6.5-5Z"
                      stroke="currentColor"
                      strokeWidth="1.2"
                      strokeLinejoin="round"
                    />
                    <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.2" />
                    <path d="M2 14 14 2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                  </svg>
                )}
              </button>
            </div>
          </div>
          {message ? <p className="form-hint auth-message">{message}</p> : null}
          <div className="modal-ctas">
            <button className="btn btn-primary" type="submit" disabled={busy}>
              {busy ? "Working..." : mode === "login" ? "Sign in" : "Create account"}
            </button>
          </div>
        </form>

        <button
          className="auth-switch"
          type="button"
          onClick={() => {
            setMode(mode === "login" ? "signup" : "login");
            setMessage(null);
          }}
        >
          {mode === "login" ? "Need an account? Create one" : "Already have an account? Sign in"}
        </button>

        <p className="modal-disclaimer">
          Priva can trade in the paper environment but can never withdraw funds.
        </p>
      </div>
    </div>
  );
}