"use client";

import { useState } from "react";
import ConnectModal from "@/components/ConnectModal";

export default function Hero() {
  const [isModalOpen, setIsModalOpen] = useState(false);

  return (
    <section className="hero">
      <div className="hero-top">
        <div
          className="hero-image"
          role="img"
          aria-label="Detail of a vault locking mechanism"
        />
        <div className="wrap">
          <div className="hero-eyebrow">
            Tokenized U.S. equities — spot &amp; leveraged perps
          </div>
          <h1 className="hero-headline">
            An agent that trades for you, and tells no one it did.
          </h1>
          <p className="hero-sub">
            Priva executes your strategy autonomously and submits every order
            as an encrypted intent. Your positions stay off the public book
            until they&apos;re filled.
          </p>
          <div className="hero-ctas">
            <button
              className="btn btn-primary"
              onClick={() => setIsModalOpen(true)}
            >
              Connect account
            </button>
            <a className="btn" href="#how-it-works">
                          See how it works
                        </a>
          </div>
        </div>
      </div>

      <div className="wrap">
        <div className="ticker">
          <div className="ticker-cell">
            <div className="ticker-label">Total P&amp;L</div>
            <div className="ticker-value up">+$18,240.12</div>
          </div>
          <div className="ticker-cell">
            <div className="ticker-label">Today</div>
            <div className="ticker-value up">+$412.30</div>
          </div>
          <div className="ticker-cell">
            <div className="ticker-label">Win rate</div>
            <div className="ticker-value">61.4%</div>
          </div>
          <div className="ticker-cell">
            <div className="ticker-label">Max drawdown</div>
            <div className="ticker-value down">−6.8%</div>
          </div>
        </div>
      </div>

      <ConnectModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
    </section>
  );
}