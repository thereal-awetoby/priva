"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";

type BacktestMetrics = {
  return_pct?: number;
  sharpe?: number;
  max_drawdown_pct?: number;
  win_rate_pct?: number;
};

function BacktestResult({ metrics }: { metrics: BacktestMetrics }) {
  return (
    <div className="backtest-result">
      <div className="backtest-result-title">Backtest result</div>
      <div className="backtest-metrics">
        <div>
          <div className="backtest-metric-label">Return</div>
          <div className="backtest-metric-value up">
            {metrics.return_pct != null ? `${metrics.return_pct}%` : "—"}
          </div>
        </div>
        <div>
          <div className="backtest-metric-label">Sharpe</div>
          <div className="backtest-metric-value">
            {metrics.sharpe ?? "—"}
          </div>
        </div>
        <div>
          <div className="backtest-metric-label">Max drawdown</div>
          <div className="backtest-metric-value down">
            {metrics.max_drawdown_pct != null
              ? `${metrics.max_drawdown_pct}%`
              : "—"}
          </div>
        </div>
        <div>
          <div className="backtest-metric-label">Win rate</div>
          <div className="backtest-metric-value">
            {metrics.win_rate_pct != null ? `${metrics.win_rate_pct}%` : "—"}
          </div>
        </div>
      </div>
    </div>
  );
}

function PlainEnglishForm() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BacktestMetrics | null>(null);

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await apiPost<any>("/strategies/parse", {
        text,
        use_gemini: true,
      });
      console.log("PARSE RESPONSE:", data);
      setResult(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="form-block">
      <div className="form-field">
        <label className="form-label">Describe your strategy</label>
        <textarea
          className="form-textarea"
          placeholder="e.g. Buy AAPL when RSI drops below 30, sell when it rises above 70"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <div className="form-hint">
          Only AAPL and TSLA are supported in the paper environment right now.
        </div>
      </div>

      <button
        className="btn btn-primary"
        onClick={handleGenerate}
        disabled={loading || text.trim() === ""}
      >
        {loading ? "Generating…" : "Generate & Backtest"}
      </button>

      {error && (
        <div className="form-hint" style={{ marginTop: "14px", color: "var(--down)" }}>
          {error}
        </div>
      )}

      {result && <BacktestResult metrics={result} />}
    </div>
  );
}

function StructuredForm() {
  const [entryCondition, setEntryCondition] = useState("");
  const [exitCondition, setExitCondition] = useState("");
  const [positionSize, setPositionSize] = useState("");
  const [maxLeverage, setMaxLeverage] = useState("");
  const [stopLoss, setStopLoss] = useState("");
  const [takeProfit, setTakeProfit] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BacktestMetrics | null>(null);

  const handleBacktest = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await apiPost<any>("/strategies/parse", {
        entry_condition: entryCondition,
        exit_condition: exitCondition,
        position_size: positionSize,
        max_leverage: maxLeverage,
        stop_loss: stopLoss,
        take_profit: takeProfit,
        use_gemini: true,
      });
      console.log("STRUCTURED STRATEGY RESPONSE:", data);
      setResult(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="form-block">
      <div className="form-field">
        <label className="form-label">Entry condition</label>
        <input
          className="form-input"
          placeholder="e.g. RSI below 30"
          value={entryCondition}
          onChange={(e) => setEntryCondition(e.target.value)}
        />
      </div>
      <div className="form-field">
        <label className="form-label">Exit condition</label>
        <input
          className="form-input"
          placeholder="e.g. RSI above 70"
          value={exitCondition}
          onChange={(e) => setExitCondition(e.target.value)}
        />
      </div>
      <div className="form-row-split">
        <div className="form-field">
          <label className="form-label">Position size</label>
          <input
            className="form-input"
            placeholder="e.g. 10% of portfolio"
            value={positionSize}
            onChange={(e) => setPositionSize(e.target.value)}
          />
        </div>
        <div className="form-field">
          <label className="form-label">Max leverage</label>
          <input
            className="form-input"
            placeholder="e.g. 2x"
            value={maxLeverage}
            onChange={(e) => setMaxLeverage(e.target.value)}
          />
        </div>
      </div>
      <div className="form-row-split">
        <div className="form-field">
          <label className="form-label">Stop loss</label>
          <input
            className="form-input"
            placeholder="e.g. 5%"
            value={stopLoss}
            onChange={(e) => setStopLoss(e.target.value)}
          />
        </div>
        <div className="form-field">
          <label className="form-label">Take profit</label>
          <input
            className="form-input"
            placeholder="e.g. 12%"
            value={takeProfit}
            onChange={(e) => setTakeProfit(e.target.value)}
          />
        </div>
      </div>

      <button
        className="btn btn-primary"
        onClick={handleBacktest}
        disabled={loading}
      >
        {loading ? "Running backtest…" : "Run backtest"}
      </button>

      {error && (
        <div className="form-hint" style={{ marginTop: "14px", color: "var(--down)" }}>
          {error}
        </div>
      )}

      {result && <BacktestResult metrics={result} />}
    </div>
  );
}

export default function CustomStrategyTab() {
  const [subTab, setSubTab] = useState<"plain-english" | "form">(
    "plain-english"
  );

  return (
    <div>
      <div className="custom-subtabs">
        <button
          className={subTab === "plain-english" ? "active" : ""}
          onClick={() => setSubTab("plain-english")}
        >
          Plain English
        </button>
        <button
          className={subTab === "form" ? "active" : ""}
          onClick={() => setSubTab("form")}
        >
          Form
        </button>
      </div>

      {subTab === "plain-english" ? <PlainEnglishForm /> : <StructuredForm />}
    </div>
  );
}