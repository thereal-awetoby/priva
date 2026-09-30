"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";

type ConnectResponse = {
  status?: string;
  demo_verified?: boolean;
  position_mode?: string;
};

type ConnectAccountFormProps = {
  onConnected: (positionMode?: string) => void;
  submitLabel?: string;
};

export default function ConnectAccountForm({
  onConnected,
  submitLabel = "Verify and connect",
}: ConnectAccountFormProps) {
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [passphrase, setPassphrase] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setConnecting(true);
    setError(null);
    try {
      const result = await apiPost<ConnectResponse>("/account/connect", {
        api_key: apiKey.trim(),
        api_secret: apiSecret.trim(),
        passphrase: passphrase.trim(),
      });
      if (result.status !== "connected" || result.demo_verified !== true) {
        throw new Error("Bitget did not verify these credentials for paper trading.");
      }
      setApiKey("");
      setApiSecret("");
      setPassphrase("");
      onConnected(result.position_mode);
    } catch (connectError) {
      setError(connectError instanceof Error ? connectError.message : "Unable to verify the Bitget account.");
    } finally {
      setConnecting(false);
    }
  };

  return (
    <form className="account-connect-form" onSubmit={submit}>
      <div className="form-field">
        <label className="form-label" htmlFor="bitget-api-key">API key</label>
        <input
          id="bitget-api-key"
          className="form-input"
          name="api_key"
          type="text"
          autoComplete="off"
          required
          value={apiKey}
          onChange={(event) => setApiKey(event.target.value)}
        />
      </div>
      <div className="form-field">
        <label className="form-label" htmlFor="bitget-api-secret">API secret</label>
        <input
          id="bitget-api-secret"
          className="form-input"
          name="api_secret"
          type="password"
          autoComplete="new-password"
          required
          value={apiSecret}
          onChange={(event) => setApiSecret(event.target.value)}
        />
      </div>
      <div className="form-field">
        <label className="form-label" htmlFor="bitget-api-passphrase">Passphrase</label>
        <input
          id="bitget-api-passphrase"
          className="form-input"
          name="passphrase"
          type="password"
          autoComplete="new-password"
          required
          value={passphrase}
          onChange={(event) => setPassphrase(event.target.value)}
        />
      </div>
      <p className="account-connect-hint">
        In Bitget Demo Trading, create a key under API Management and grant only read and trade permissions.
      </p>
      <p className="account-connect-notice">
        Demo/paper credentials only. Live-account credentials are rejected. Credentials are encrypted before storage and never returned to your browser.
      </p>
      {error ? <p className="account-connect-error" role="alert">{error}</p> : null}
      <button className="btn btn-primary account-connect-submit" type="submit" disabled={connecting}>
        {connecting ? "Verifying paper account…" : submitLabel}
      </button>
    </form>
  );
}
