import { Bell, LogOut, Menu, Search } from "lucide-react";
import { useState } from "react";
import { useLocation } from "react-router-dom";

import { useAuth } from "../../features/auth/useAuth";

const pageTitles = {
  "/dashboard": "Overview",
  "/problems": "Problem library",
  "/visualizer": "Algorithm visualizer",
  "/compare": "Algorithm comparison",
  "/interviews": "Interview simulator",
  "/analytics": "Learning analytics",
  "/settings": "Workspace settings",
};

function initialsFor(name) {
  const parts = String(name || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (!parts.length) return "GL";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

export default function Topbar({ onMenu }) {
  const location = useLocation();
  const { logout, user } = useAuth();
  const [signingOut, setSigningOut] = useState(false);
  const basePath = Object.keys(pageTitles).find((path) => location.pathname.startsWith(path));
  const title = basePath ? pageTitles[basePath] : "Problem workspace";

  async function handleLogout() {
    setSigningOut(true);
    try {
      await logout();
    } finally {
      setSigningOut(false);
    }
  }

  return (
    <header className="topbar">
      <button aria-label="Open navigation" className="icon-button menu-button" onClick={onMenu} type="button">
        <Menu size={20} />
      </button>
      <div className="topbar-heading">
        <span className="eyebrow">Learning workspace</span>
        <h1>{title}</h1>
      </div>
      <div className="topbar-actions">
        <label className="search-box">
          <Search size={16} />
          <span className="sr-only">Search</span>
          <input aria-label="Search problems" placeholder="Search problems" type="search" />
          <kbd>⌘ K</kbd>
        </label>
        <button aria-label="Notifications" className="icon-button notification-button" type="button">
          <Bell size={18} />
          <span className="notification-dot" />
        </button>
        <div className="user-chip">
          <div className="avatar" aria-hidden="true">
            {initialsFor(user?.name)}
          </div>
          <div className="user-meta">
            <strong>{user?.name}</strong>
            <span>{user?.email}</span>
          </div>
        </div>
        <button
          aria-label="Sign out"
          className="icon-button"
          disabled={signingOut}
          onClick={handleLogout}
          title="Sign out"
          type="button"
        >
          <LogOut size={17} />
        </button>
      </div>
    </header>
  );
}
