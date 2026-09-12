type SidebarProps = {
    activeTab: string;
    onTabChange: (tab: string) => void;
  };
  
  const navItems = [
    {
      id: "control",
      label: "Control center",
      icon: (
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.3" />
          <path d="M8 8L10.2 5.6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
        </svg>
      ),
    },
    {
      id: "strategy",
      label: "Strategy lab",
      icon: (
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="4" r="1.6" stroke="currentColor" strokeWidth="1.2" />
          <circle cx="4" cy="12" r="1.6" stroke="currentColor" strokeWidth="1.2" />
          <circle cx="12" cy="12" r="1.6" stroke="currentColor" strokeWidth="1.2" />
          <path d="M8 5.6V8M8 8L4 10.6M8 8L12 10.6" stroke="currentColor" strokeWidth="1.2" />
        </svg>
      ),
    },
    {
      id: "risk",
      label: "Risk & access",
      icon: (
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path
            d="M8 2.2L13 4V7.6C13 11 10.8 13 8 13.8C5.2 13 3 11 3 7.6V4L8 2.2Z"
            stroke="currentColor"
            strokeWidth="1.2"
            strokeLinejoin="round"
          />
        </svg>
      ),
    },
    {
      id: "activity",
      label: "Activity",
      icon: (
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path
            d="M2 8.5H5L6.3 5L9.2 11.5L10.5 8.5H14"
            stroke="currentColor"
            strokeWidth="1.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      ),
    },
  ];
  
  export default function Sidebar({ activeTab, onTabChange }: SidebarProps) {
    return (
      <aside className="app-sidebar">
        <div className="sidebar-top">
          <div className="wordmark">
            Pr<span>i</span>va
          </div>
          <div className="env-dot" title="System nominal" />
        </div>
  
        <div className="sidebar-section-label">Workspace</div>
        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${activeTab === item.id ? "active" : ""}`}
              onClick={() => onTabChange(item.id)}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </nav>
  
        <div className="sidebar-bottom">
          <div className="connection-card">
            <div className="connection-label">Connection</div>
            <div className="connection-row">
              <div className="connection-mark">B</div>
              <div>
                <div className="connection-name">Bitget</div>
                <div className="connection-sub">•••• 8F2A</div>
              </div>
              <div className="connection-dot" />
            </div>
          </div>
          <div className="profile-row">
            <div className="profile-avatar">J</div>
            <div>
              <div className="profile-name">Jordan S.</div>
              <div className="profile-sub">Private workspace</div>
            </div>
          </div>
        </div>
      </aside>
    );
  }