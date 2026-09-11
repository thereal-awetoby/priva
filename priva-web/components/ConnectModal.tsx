type ConnectModalProps = {
  isOpen: boolean;
  onClose: () => void;
};

export default function ConnectModal({ isOpen, onClose }: ConnectModalProps) {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose} aria-label="Close">
          Close ✕
        </button>

        <h2 className="modal-title">Get started with Priva</h2>
        <p className="modal-sub">
          Connect a Bitget account to start paper trading — no funds
          required to begin.
        </p>

        <div className="modal-ctas">
          <a className="btn btn-primary" href="#dashboard">
            Connect Bitget
          </a>
        </div>

        <p className="modal-disclaimer">
          Priva trades on your behalf but can never withdraw funds.
        </p>
      </div>
    </div>
  );
}