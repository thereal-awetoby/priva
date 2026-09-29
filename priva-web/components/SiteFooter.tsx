export default function SiteFooter() {
  const iconStyle = { width: 20, height: 20, fill: "currentColor" };
  const linkStyle = { display: "flex", color: "inherit" };

  return (
    <footer>
      <div
        className="wrap footer"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          width: "100%",
        }}
      >
        <span>Priva</span>

        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <span>Built for Bitget S2 Hackathon</span>

          <a href="https://github.com/thereal-awetoby/priva" target="_blank" rel="noopener noreferrer" aria-label="Priva on GitHub" style={linkStyle}>
            <svg viewBox="0 0 24 24" style={iconStyle} aria-hidden="true">
              <path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.1.79-.25.79-.56v-2c-3.2.7-3.87-1.36-3.87-1.36-.52-1.33-1.28-1.69-1.28-1.69-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.18 1.76 1.18 1.03 1.76 2.69 1.25 3.35.96.1-.75.4-1.25.73-1.54-2.55-.29-5.24-1.28-5.24-5.68 0-1.25.45-2.28 1.18-3.08-.12-.29-.51-1.46.11-3.05 0 0 .97-.31 3.17 1.18a11 11 0 0 1 5.77 0c2.2-1.49 3.17-1.18 3.17-1.18.62 1.59.23 2.76.11 3.05.74.8 1.18 1.83 1.18 3.08 0 4.41-2.69 5.38-5.25 5.67.41.36.78 1.06.78 2.14v3.17c0 .31.21.67.8.56A11.5 11.5 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5Z" />
            </svg>
          </a>

          <a href="https://x.com/winsoonbob?s=11" target="_blank" rel="noopener noreferrer" aria-label="Priva on X" style={linkStyle}>
            <svg viewBox="0 0 24 24" style={iconStyle} aria-hidden="true">
              <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817-5.97 6.817H1.675l7.73-8.835L1.254 2.25H8.08l4.713 6.231 5.451-6.231Zm-1.161 17.52h1.833L7.084 4.126H5.117L17.083 19.77Z" />
            </svg>
          </a>
        </div>
      </div>
    </footer>
  );
}