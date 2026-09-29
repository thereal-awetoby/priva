export default function Masthead() {
  return (
    <header className="masthead">
      <div className="wrap masthead-inner">
        <div className="wordmark">
          Pr<span>i</span>va
        </div>
        <nav className="links">
          <a href="#thesis">Thesis</a>
          <a href="#privacy">Privacy</a>
          <a href="https://x.com/winsoonbob?s=11" target="_blank" rel="noopener noreferrer">
            Demo
          </a>
        </nav>
        <a href="/app" className="btn btn-primary" target="_blank" rel="noopener noreferrer">
          Launch app
        </a>
      </div>
    </header>
  );
}