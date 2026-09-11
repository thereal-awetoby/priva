export default function DashboardPreview() {
  return (
    <section className="dash-section" id="dashboard">
      <div className="wrap">
        <div className="dash-heading">
          <h2>The dashboard</h2>
          <span>Live preview — sample data</span>
        </div>

        <div className="device">
          <div className="app-topbar">
            <div className="app-brand">
              <div className="wordmark">
                Pr<span>i</span>va
              </div>
              <div className="status-pill">
                <span className="status-dot" />
                Running
              </div>
            </div>
            <div className="mode-switch">
              <button className="active">Autonomous</button>
              <button>Strategy</button>
            </div>
          </div>

          <div className="app-body">
            <div className="perf-row">
              <div className="perf-cell">
                <div className="perf-label">Total P&amp;L</div>
                <div className="perf-value up">+$18,240.12</div>
              </div>
              <div className="perf-cell">
                <div className="perf-label">Today&apos;s P&amp;L</div>
                <div className="perf-value up">+$412.30</div>
              </div>
              <div className="perf-cell">
                <div className="perf-label">Win rate</div>
                <div className="perf-value">61.4%</div>
              </div>
              <div className="perf-cell">
                <div className="perf-label">Max drawdown</div>
                <div className="perf-value down">−6.8%</div>
              </div>
            </div>

            <div className="risk-row">
              <div className="risk-label-row">
                <span>Risk usage</span>
                <span>42% of daily limit</span>
              </div>
              <div className="risk-bar">
                <div className="risk-bar-fill" style={{ width: "42%" }} />
              </div>
            </div>

            <div className="split">
              <div>
                <div className="panel-title">Positions</div>
                <table className="positions">
                  <thead>
                    <tr>
                      <th>Asset</th>
                      <th>Side</th>
                      <th>Size</th>
                      <th>P&amp;L</th>
                      <th>Type</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>NVDA</td>
                      <td>
                        <span className="side-tag up">Long 2x</span>
                      </td>
                      <td>$4,200.00</td>
                      <td className="up">+$182.40</td>
                      <td>Perp</td>
                    </tr>
                    <tr>
                      <td>TSLA</td>
                      <td>
                        <span className="side-tag down">Short 1.5x</span>
                      </td>
                      <td>$2,800.00</td>
                      <td className="down">−$64.10</td>
                      <td>Perp</td>
                    </tr>
                    <tr>
                      <td>AAPL</td>
                      <td>
                        <span className="side-tag up">Long</span>
                      </td>
                      <td>$1,500.00</td>
                      <td className="up">+$22.05</td>
                      <td>Spot</td>
                    </tr>
                  </tbody>
                </table>

                <div className="app-actions">
                  <a className="btn" href="#">
                    Pause
                  </a>
                  <a className="btn btn-danger" href="#">
                    Kill switch
                  </a>
                </div>
              </div>

              <div>
                <div className="panel-title">Recent activity</div>
                <div className="activity-log">
                  <div className="log-row">
                    <span className="log-time">14:02</span>
                    <span>Encrypted intent submitted — NVDA long 2x</span>
                  </div>
                  <div className="log-row">
                    <span className="log-time">14:02</span>
                    <span>Trade filled at $121.84</span>
                  </div>
                  <div className="log-row">
                    <span className="log-time">13:47</span>
                    <span>Risk limit check passed</span>
                  </div>
                  <div className="log-row">
                    <span className="log-time">13:15</span>
                    <span>Encrypted intent submitted — TSLA short 1.5x</span>
                  </div>
                  <div className="log-row">
                    <span className="log-time">11:30</span>
                    <span>Strategy mode → Autonomous</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}