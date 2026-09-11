import Link from "next/link";

export default function Masthead() {
  return (
    <header className="masthead">
      <div className="wrap masthead-inner">
        <div className="wordmark">
          Pr<span>i</span>va
        </div>
        <nav className="links">
          <a href="#dashboard">Dashboard</a>
          <a href="#">Security</a>
          <a href="#">Docs</a>
        </nav>
        <Link className="btn btn-primary" href="#dashboard">
          Launch app
        </Link>
      </div>
    </header>
  );
}