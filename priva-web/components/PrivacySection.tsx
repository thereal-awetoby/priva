const rows = [
    {
      num: "01",
      title: "Agent decides privately",
      body: "The strategy stays inside the private core, never exposed to the wider market.",
    },
    {
      num: "02",
      title: "Creates an encrypted intent",
      body: "The instruction is protected before it ever reaches the order book.",
    },
    {
      num: "03",
      title: "Only limited permissions are used",
      body: "Trading access only. Withdrawal access is never granted.",
    },
    {
      num: "04",
      title: "Hard risk limits, always on",
      body: "You define the edges. A kill switch lets you stop execution at any time.",
    },
  ];
  
  export default function PrivacySection() {
    return (
      <section className="content-section">
        <div className="wrap content-split">
          <div>
            <div className="content-eyebrow">Why privacy matters</div>
            <h2 className="content-heading">The edge stays protected.</h2>
            <p className="content-lead">
              Most trading agents expose their strategy in the open — anyone
              can watch, copy, or trade ahead of them.
            </p>
            <p className="content-lead">
              Priva keeps the strategy private. When it acts, it submits an
              encrypted intent instead of a visible order, so the edge stays
              protected while the agent runs around the clock.
            </p>
          </div>
          <div className="list-block">
            {rows.map((r) => (
              <div className="list-row" key={r.num}>
                <div className="list-num">{r.num}</div>
                <div>
                  <h4>{r.title}</h4>
                  <p>{r.body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    );
  }