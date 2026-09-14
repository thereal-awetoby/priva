"use client";

import { useState } from "react";

const STORAGE_KEY = "priva_onboarding_complete";

const steps = [
  {
    title: "Welcome to Priva",
    body: "An agent that trades tokenized U.S. equities for you, autonomously — while keeping your strategy private.",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.3" />
        <path d="M10 6V10L12.5 12" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    title: "Private by design",
    body: "Every order leaves as an encrypted intent, not a visible signal — so your positions stay off the public book until they're filled.",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M10 2.5L16 5V10C16 14 13 17 10 18C7 17 4 14 4 10V5L10 2.5Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    title: "Bounded by you",
    body: "Set your position size, daily loss, and leverage caps before anything runs. A kill switch is always one press away.",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M4 16H16M6 16V9M10 16V4M14 16V11" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    title: "Start with paper trading",
    body: "Explore the Control Center, Strategy Lab, and Risk & Access tabs freely — everything runs in a paper environment first, no real funds required.",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M4 4H16V16H4V4Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
        <path d="M7 8H13M7 11H13M7 14H10" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" />
      </svg>
    ),
  },
];

export default function OnboardingModal({ onClose }: { onClose: () => void }) {
  const [step, setStep] = useState(0);
  const isLast = step === steps.length - 1;

  const finish = () => {
    try {
      localStorage.setItem(STORAGE_KEY, "true");
    } catch {
      // localStorage unavailable — not critical, modal just reappears next visit
    }
    onClose();
  };

  const current = steps[step];

  return (
    <div className="modal-overlay" onClick={finish}>
      <div
        className="modal-panel onboarding-panel"
        onClick={(e) => e.stopPropagation()}
      >
        <button className="modal-close" onClick={finish} aria-label="Close">
          Close ✕
        </button>

        <div className="onboarding-step-icon">{current.icon}</div>
        <h2 className="modal-title">{current.title}</h2>
        <p className="modal-sub">{current.body}</p>

        <div className="onboarding-dots">
          {steps.map((_, i) => (
            <button
              key={i}
              className={`onboarding-dot ${i === step ? "active" : ""}`}
              onClick={() => setStep(i)}
              aria-label={`Go to step ${i + 1}`}
            />
          ))}
        </div>

        <div className="onboarding-nav">
          <button className="onboarding-skip" onClick={finish}>
            Skip
          </button>
          {isLast ? (
            <button className="btn btn-primary" onClick={finish}>
              Get started
            </button>
          ) : (
            <button className="btn btn-primary" onClick={() => setStep(step + 1)}>
              Next
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function hasSeenOnboarding(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}