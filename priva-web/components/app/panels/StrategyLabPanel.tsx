"use client";

import { useState } from "react";
import PrebuiltTab from "@/components/app/panels/strategy/PrebuiltTab";
import PlaybookTab from "@/components/app/panels/strategy/PlaybookTab";
import CustomStrategyTab from "@/components/app/panels/strategy/CustomStrategyTab";

export default function StrategyLabPanel() {
  const [tab, setTab] = useState<"prebuilt" | "playbook" | "custom">(
    "prebuilt"
  );

  return (
    <div>
      <div className="panel-eyebrow">Decision engine</div>
      <h2 className="panel-heading">Build the way Priva thinks.</h2>
      <p className="panel-lead">
        Choose a bounded strategy or shape your own. Every rule is visible
        before it can act.
      </p>

      <div className="custom-subtabs" style={{ marginBottom: "26px" }}>
        <button
          className={tab === "prebuilt" ? "active" : ""}
          onClick={() => setTab("prebuilt")}
        >
          Pre-built
        </button>
        <button
          className={tab === "playbook" ? "active" : ""}
          onClick={() => setTab("playbook")}
        >
          Playbook
        </button>
        <button
          className={tab === "custom" ? "active" : ""}
          onClick={() => setTab("custom")}
        >
          My Custom
        </button>
      </div>

      {tab === "prebuilt" && <PrebuiltTab />}
      {tab === "playbook" && <PlaybookTab />}
      {tab === "custom" && <CustomStrategyTab />}
    </div>
  );
}