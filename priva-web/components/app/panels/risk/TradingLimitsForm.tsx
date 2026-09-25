"use client";

import { useState, useEffect } from "react";
import { apiGet, apiPost } from "@/lib/api";

const SUPPORTED_SYMBOLS = ["AAPL", "TSLA"];

export default function TradingLimitsForm() {
  const [maxPositionSize, setMaxPositionSize] = useState("25000");
  const [maxDailyLoss, setMaxDailyLoss] = useState("1500");
  const [maxLeverage, setMaxLeverage] = useState("2");
  const [takeProfitPct, setTakeProfitPct] = useState("3.5");
  const [stopLossPct, setStopLossPct] = useState("2");
  const [allowedSymbols, setAllowedSymbols] = useState<string[]>(SUPPORTED_SYMBOLS);
  const [agentSettings, setAgentSettings] = useState<Record<string, any>>({});

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<{ type: "success" | "error"; message: string } | null>(null);

  useEffect(() => {
    Promise.all([apiGet<any>("/risk-settings"), apiGet<any>("/user/agent-settings")])
      .then(([data, userData]) => {
        if (data.max_position_size != null) setMaxPositionSize(String(data.max_position_size));
        if (data.max_daily_loss != null) setMaxDailyLoss(String(data.max_daily_loss));
        if (data.max_leverage != null) setMaxLeverage(String(data.max_leverage));
        if (data.allowed_symbols) setAllowedSymbols(data.allowed_symbols);
        if (userData.take_profit_pct != null) setTakeProfitPct(String(userData.take_profit_pct));
        if (userData.stop_loss_pct != null) setStopLossPct(String(userData.stop_loss_pct));
        if (userData.max_leverage != null) setMaxLeverage(String(userData.max_leverage));
        setAgentSettings(userData);
        setLoading(false);
      })
      .catch((err) => {
        setLoading(false);
      });
  }, []);

  const toggleSymbol = (symbol: string) => {
    setAllowedSymbols((prev) =>
      prev.includes(symbol) ? prev.filter((s) => s !== symbol) : [...prev, symbol]
    );
  };

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);
    try {
      await apiPost("/risk-settings", {
        max_position_size: Number(maxPositionSize),
        max_daily_loss: Number(maxDailyLoss),
        max_leverage: Number(maxLeverage),
        allowed_symbols: allowedSymbols,
      });
      await apiPost("/user/agent-settings", {
        market: agentSettings.market ?? "futures",
        take_profit_pct: Number(takeProfitPct),
        stop_loss_pct: Number(stopLossPct),
        close_on_signal_violation: agentSettings.close_on_signal_violation ?? true,
        symbols: agentSettings.symbols ?? ["AAPLUSDT", "TSLAUSDT"],
        strategy_id: agentSettings.strategy_id ?? null,
        strategy_by_symbol: agentSettings.strategy_by_symbol ?? null,
        max_position_size: Number(maxPositionSize),
        max_daily_loss: Number(maxDailyLoss),
        max_leverage: Number(maxLeverage),
        risk_enabled: agentSettings.risk_enabled ?? true,
        allowed_symbols: agentSettings.allowed_symbols ?? allowedSymbols,
      });
      setStatus({ type: "success", message: "Settings saved." });
    } catch (err: any) {
      setStatus({ type: "error", message: err.message });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <p className="panel-lead">Loading current limits…</p>;
  }

  return (
    <div className="limits-form">
            <h3>Set your own boundaries</h3>
      <p className="limits-form-sub">
        These aren&apos;t suggestions — every trade is checked against them before
        it&apos;s allowed to happen.
      </p>

      <div className="slider-row">
        <div className="slider-label-row">
          <label className="form-label">Max position size</label>
          <span className="slider-value">${Number(maxPositionSize).toLocaleString()}</span>
        </div>
        <input
          className="form-slider"
          type="range"
          min="1000"
          max="50000"
          step="500"
          value={maxPositionSize}
          onChange={(e) => setMaxPositionSize(e.target.value)}
        />
      </div>

      <div className="slider-row">
        <div className="slider-label-row">
          <label className="form-label">Max daily loss</label>
          <span className="slider-value">${Number(maxDailyLoss).toLocaleString()}</span>
        </div>
        <input
          className="form-slider"
          type="range"
          min="100"
          max="5000"
          step="100"
          value={maxDailyLoss}
          onChange={(e) => setMaxDailyLoss(e.target.value)}
        />
      </div>

      <div className="slider-row">
        <div className="slider-label-row">
          <label className="form-label">Max leverage</label>
          <span className="slider-value">{maxLeverage}x</span>
        </div>
        <input
          className="form-slider"
          type="range"
          min="1"
          max="10"
          step="0.5"
          value={maxLeverage}
          onChange={(e) => setMaxLeverage(e.target.value)}
        />
      </div>

      <div className="slider-row">
        <div className="slider-label-row">
          <label className="form-label">Take profit</label>
          <span className="slider-value">{takeProfitPct}%</span>
        </div>
        <input
          className="form-slider"
          type="range"
          min="0.1"
          max="25"
          step="0.1"
          value={takeProfitPct}
          onChange={(e) => setTakeProfitPct(e.target.value)}
        />
      </div>

      <div className="slider-row">
        <div className="slider-label-row">
          <label className="form-label">Stop loss</label>
          <span className="slider-value">{stopLossPct}%</span>
        </div>
        <input
          className="form-slider"
          type="range"
          min="0.1"
          max="25"
          step="0.1"
          value={stopLossPct}
          onChange={(e) => setStopLossPct(e.target.value)}
        />
      </div>

      <div className="form-field">
        <label className="form-label">Allowed stocks</label>
        <div className="stock-toggle-list">
          {SUPPORTED_SYMBOLS.map((symbol) => (
            <button
              key={symbol}
              type="button"
              className={`stock-chip ${allowedSymbols.includes(symbol) ? "active" : ""}`}
              onClick={() => toggleSymbol(symbol)}
            >
              {symbol}
            </button>
          ))}
        </div>
                <div className="form-hint">
          AAPL and TSLA only, for now — Priva won&apos;t trade anything outside this list.
        </div>
      </div>

      <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
        {saving ? "Saving…" : "Save changes"}
      </button>

            {status && (
        <div
          className="save-status"
          style={{ color: status.type === "success" ? "var(--up)" : "var(--down)" }}
        >
          {status.type === "success" ? "Saved — new trades will respect these limits." : status.message}
        </div>
      )}
    </div>
  );
}