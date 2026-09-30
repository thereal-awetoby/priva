"use client";

import ConnectAccountForm from "@/components/app/ConnectAccountForm";

type AccountConnectScreenProps = {
  email?: string;
  onConnected: (positionMode?: string) => void;
  onSignOut: () => void;
  onRetry: () => void;
  unavailable?: boolean;
};

export default function AccountConnectScreen({
  email,
  onConnected,
  onSignOut,
  onRetry,
  unavailable = false,
}: AccountConnectScreenProps) {
  return (
    <main className="account-connect-screen">
      <header className="account-connect-header">
        <div className="wordmark">Pr<span>i</span>va</div>
        <div className="account-connect-user">
          {email ? <span>{email}</span> : null}
          <button className="sign-out-btn" type="button" onClick={onSignOut}>Sign out</button>
        </div>
      </header>
      <div className="account-connect-layout">
        <section className="account-connect-intro">
          <p className="account-connect-kicker">PRIVATE WORKSPACE / PAPER EXECUTION</p>
          <h1>Connect your Bitget demo account</h1>
          <p className="account-connect-description">
            Priva connects only to the demo trading environment. Your workspace stays locked until your own paper account is verified.
          </p>
          <div className="account-connect-proof">
            <span className="account-connect-proof-mark" aria-hidden="true">01</span>
            <span>Verified against Bitget paper trading</span>
          </div>
          <div className="account-connect-proof">
            <span className="account-connect-proof-mark" aria-hidden="true">02</span>
            <span>Stored encrypted and scoped to your Supabase account</span>
          </div>
        </section>
        <section className="account-connect-panel" aria-label="Bitget demo credentials">
          {unavailable ? (
            <div className="account-connect-unavailable" role="alert">
              <h2>Connection status unavailable</h2>
              <p>Priva could not check your account. Your dashboard remains locked.</p>
              <button className="btn" type="button" onClick={onRetry}>Retry</button>
            </div>
          ) : (
            <>
              <div className="account-connect-panel-heading">
                <span className="connection-mark" aria-hidden="true">B</span>
                <div>
                  <h2>Bitget Demo Trading</h2>
                  <p>API credentials</p>
                </div>
              </div>
              <ConnectAccountForm onConnected={onConnected} />
            </>
          )}
        </section>
      </div>
    </main>
  );
}
