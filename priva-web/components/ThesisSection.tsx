export default function ThesisSection() {
    return (
      <section className="content-section">
        <div className="wrap content-split">
          <div>
            <div className="content-eyebrow">The Priva thesis</div>
            <h2 className="content-heading">
              Autonomy should earn trust, not ask for it.
            </h2>
            <p className="content-lead">
              Every decision is visible in its outcome, even while the
              reasoning behind it stays private.
            </p>
          </div>
          <div className="card-grid">
            <div className="step-card">
              <svg
                className="step-mark"
                viewBox="0 0 28 28"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <circle cx="14" cy="14" r="9" stroke="#C79A4B" strokeWidth="1.4" />
                <path
                  d="M14 9V14L17.5 16.5"
                  stroke="#C79A4B"
                  strokeWidth="1.4"
                  strokeLinecap="round"
                />
              </svg>
              <h3>Visible by default</h3>
              <p>
                Every position, every limit, and every result lives on one
                clear dashboard — never a black box.
              </p>
            </div>
            <div className="step-card">
              <svg
                className="step-mark"
                viewBox="0 0 28 28"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M14 4L23 8V14C23 19.5 19.2 23.6 14 25C8.8 23.6 5 19.5 5 14V8L14 4Z"
                  stroke="#C79A4B"
                  strokeWidth="1.4"
                  strokeLinejoin="round"
                />
              </svg>
              <h3>Private by design</h3>
              <p>
                Your strategy and your keys stay protected. Orders leave as
                encrypted intents, not open signals.
              </p>
            </div>
            <div className="step-card">
              <svg
                className="step-mark"
                viewBox="0 0 28 28"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M4 22H24"
                  stroke="#C79A4B"
                  strokeWidth="1.4"
                  strokeLinecap="round"
                />
                <path
                  d="M8 22V13M14 22V7M20 22V16"
                  stroke="#C79A4B"
                  strokeWidth="1.4"
                  strokeLinecap="round"
                />
              </svg>
              <h3>Bounded by you</h3>
              <p>
                Position size, daily loss, and leverage caps are set before
                anything runs. A kill switch is always one press away.
              </p>
            </div>
          </div>
        </div>
      </section>
    );
  }