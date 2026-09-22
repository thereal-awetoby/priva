"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";

type ActivationResult = Record<string, any>;

const SUPPORTED_SYMBOLS = ["AAPLUSDT", "TSLAUSDT"];

function SymbolSelector({
  symbols,
  onChange,
}: {
  symbols: string[];
  onChange: (s: string[]) => void;
}) {
  const toggle = (s: string) => {
    onChange(
      symbols.includes(s) ? symbols.filter((x) => x !== s) : [...symbols, s]
    );
  };

  return (
    <div className="form-field">
      <label className="form-label">Symbols</label>
      <div className="symbol-select">
        {SUPPORTED_SYMBOLS.map((s) => (
          <button
            key={s}
            type="button"
            className={`symbol-chip ${symbols.includes(s) ? "active" : ""}`}
            onClick={() => toggle(s)}
          >
            {s.replace("USDT", "")}
          </button>
        ))}
      </div>
    </div>
  );
}

function ActivationBanner({ result }: { result: ActivationResult }) {
  return (
    <div className="backtest-result">
      <div className="backtest-result-title">
        {result.name ? `"${result.name}" is live` : "Strategy activated"}
      </div>
      <p style={{ margin: 0, fontSize: "13.5px", color: "var(--ink-dim)" }}>
        This strategy is now live on your account and will act on the next
        agent cycle. You'll find it saved in the Pre-built tab going forward.
      </p>
      <div className="config-rows" style={{ marginTop: "16px", marginBottom: 0 }}>
        <div className="config-row">
          <span className="config-key">Strategy ID</span>
          <span className="config-value">{result.strategy_id ?? "—"}</span>
        </div>
        <div className="config-row">
          <span className="config-key">Action</span>
          <span className="config-value">{result.action ?? "—"}</span>
        </div>
        <div className="config-row">
          <span className="config-key">Status</span>
          <span className="config-value">{result.status ?? "active"}</span>
        </div>
        <div className="config-row">
          <span className="config-key">Mode</span>
          <span className="config-value">{result.mode ?? "—"}</span>
        </div>
      </div>
    </div>
  );
}

async function parseAndActivate(payload: Record<string, any>): Promise<ActivationResult> {
  const parseData = await apiPost<any>("/strategies/parse", payload);
  console.log("PARSE RESPONSE:", parseData);

  const strategyId = parseData.strategy_id;
  if (!strategyId) {
    return parseData;
  }

  const activateData = await apiPost<any>(
    `/strategies/${strategyId}/activate`,
    { symbols: payload.symbols }
  );
  console.log("ACTIVATE RESPONSE:", activateData);
  return { ...parseData, ...activateData };
}

function PlainEnglishForm() {
  const [text, setText] = useState("");
  const [strategyName, setStrategyName] = useState("");
  const [symbols, setSymbols] = useState<string[]>(["AAPLUSDT"]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ActivationResult | null>(null);

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await parseAndActivate({
        text,
        use_gemini: true,
        symbols,
        ...(strategyName.trim() && { name: strategyName.trim() }),
      });
      setResult(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="form-block">
      <SymbolSelector symbols={symbols} onChange={setSymbols} />

      <div className="form-field">
        <label className="form-label">Name it (optional)</label>
        <input
          className="form-input"
          placeholder="e.g. AAPL Dip Buyer"
          value={strategyName}
          onChange={(e) => setStrategyName(e.target.value)}
        />
        <div className="form-hint">
          Give it a name so it's easy to find in your Pre-built list later.
        </div>
      </div>

      <div className="form-field">
        <label className="form-label">Describe your strategy</label>
        <textarea
          className="form-textarea"
          placeholder="e.g. Buy when price rises 1% above today's open, sell when it falls 1% below"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <div className="form-hint">
          Only AAPL and TSLA are supported right now. This will run live on
          your demo account — not a simulation.
        </div>
      </div>

      <button
        className="btn btn-primary"
        onClick={handleGenerate}
        disabled={loading || text.trim() === "" || symbols.length === 0}
      >
        {loading ? "Creating…" : "Create & Activate"}
      </button>

      {error && (
        <div className="form-hint" style={{ marginTop: "14px", color: "var(--down)" }}>
          {error}
        </div>
      )}

      {result && <ActivationBanner result={result} />}
    </div>
  );
}

function JsonStrategyForm() {
  const [jsonText, setJsonText] = useState(
    JSON.stringify(
      {
        action: "buy",
        comparison: "open",
        threshold_pct: 1.0,
        position_size: 1.0,
        leverage: 1.0,
        take_profit_pct: 5.0,
        stop_loss_pct: 2.0,
      },
      null,
      2
    )
  );
  const [strategyName, setStrategyName] = useState("");
  const [symbols, setSymbols] = useState<string[]>(["AAPLUSDT"]);
  const [parseError, setParseError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ActivationResult | null>(null);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      setJsonText(String(reader.result));
      setParseError(null);
    };
    reader.readAsText(file);
  };

  const handleSubmit = async () => {
    let parsed: any;
    try {
      parsed = JSON.parse(jsonText);
      setParseError(null);
    } catch (err: any) {
      setParseError(`That's not valid JSON: ${err.message}`);
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await parseAndActivate({
        strategy: parsed,
        symbols,
        ...(strategyName.trim() && { name: strategyName.trim() }),
      });
      setResult(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="form-block">
      <SymbolSelector symbols={symbols} onChange={setSymbols} />

      <div className="form-field">
        <label className="form-label">Name it (optional)</label>
        <input
          className="form-input"
          placeholder="e.g. Gap Reversion v2"
          value={strategyName}
          onChange={(e) => setStrategyName(e.target.value)}
        />
      </div>

      <div className="form-field">
        <label className="form-label">Strategy rules (JSON)</label>
        <textarea
          className="form-textarea"
          style={{ fontFamily: "var(--font-ibm-plex-mono), monospace", minHeight: "180px" }}
          value={jsonText}
          onChange={(e) => setJsonText(e.target.value)}
        />
        {parseError && (
          <div className="form-hint" style={{ color: "var(--down)", marginTop: "8px" }}>
            {parseError}
          </div>
        )}
        <div className="form-hint" style={{ marginTop: "8px" }}>
          Required: action ("buy"/"sell"), comparison ("open"/"close"),
          threshold_pct. Optional: position_size, leverage, take_profit_pct,
          stop_loss_pct. This will run live on your account.
        </div>
      </div>

      <div className="form-field">
        <label className="form-label">Or upload a saved .json file</label>
        <input
          type="file"
          accept="application/json,.json"
          onChange={handleFileUpload}
          className="form-input"
          style={{ padding: "8px" }}
        />
      </div>

      <button
        className="btn btn-primary"
        onClick={handleSubmit}
        disabled={loading || symbols.length === 0}
      >
        {loading ? "Creating…" : "Create & Activate"}
      </button>

      {error && (
        <div className="form-hint" style={{ marginTop: "14px", color: "var(--down)" }}>
          {error}
        </div>
      )}

      {result && <ActivationBanner result={result} />}
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
          JSON
        </button>
      </div>

      {subTab === "plain-english" ? <PlainEnglishForm /> : <JsonStrategyForm />}
    </div>
  );
}