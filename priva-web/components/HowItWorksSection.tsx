const steps = [
    {
      index: "01",
      title: "Connect",
      body: "Link your Bitget account with limited permissions only. Priva can trade, but it can never withdraw.",
    },
    {
      index: "02",
      title: "Set boundaries",
      body: "Define position size, daily loss, leverage, and allowed assets. Choose Autonomous or Strategy mode.",
    },
    {
      index: "03",
      title: "Let it run",
      body: "The agent watches the market and executes through encrypted intents, while a kill switch stays within reach.",
    },
  ];
  
  export default function HowItWorksSection() {
    return (
      <section className="content-section">
        <div className="wrap content-split">
          <div>
            <div className="content-eyebrow">How Priva works</div>
            <h2 className="content-heading">
              Automation should feel like a cockpit, not a black box.
            </h2>
            <p className="content-lead">
              You set the boundaries. Priva stays inside them, from the first
              connection to the last trade.
            </p>
          </div>
          <div className="card-grid">
            {steps.map((s) => (
              <div className="step-card" key={s.index}>
                <div className="step-index">{s.index}</div>
                <h3>{s.title}</h3>
                <p>{s.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    );
  }