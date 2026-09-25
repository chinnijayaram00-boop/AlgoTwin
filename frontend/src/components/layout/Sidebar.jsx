import {
  BarChart3,
  GitCompareArrows,
  LayoutDashboard,
  ListChecks,
  MessagesSquare,
  Settings2,
  Waypoints,
} from "lucide-react";
import { NavLink } from "react-router-dom";

import { navigationItems, settingsItems } from "../../app/navigation";
import BrandMark from "./BrandMark";

const iconMap = {
  dashboard: LayoutDashboard,
  problems: ListChecks,
  visualizer: Waypoints,
  compare: GitCompareArrows,
  interviews: MessagesSquare,
  analytics: BarChart3,
  settings: Settings2,
};

function NavIcon({ name }) {
  const Icon = iconMap[name] || ListChecks;
  return <Icon size={18} strokeWidth={1.8} />;
}

function NavSection({ items, label, onNavigate }) {
  return (
    <div className="nav-section">
      {label ? <p className="nav-label">{label}</p> : null}
      <div className="nav-list">
        {items.map((item) => (
          <NavLink
            className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}
            end={item.to === "/dashboard"}
            key={item.to}
            onClick={onNavigate}
            to={item.to}
          >
            <NavIcon name={item.icon} />
            <span>{item.label}</span>
          </NavLink>
        ))}
      </div>
    </div>
  );
}

export default function Sidebar({ mobileOpen, onClose }) {
  return (
    <>
      {mobileOpen ? <button aria-label="Close navigation" className="sidebar-scrim" onClick={onClose} /> : null}
      <aside className={`sidebar${mobileOpen ? " mobile-open" : ""}`}>
        <div className="sidebar-header">
          <BrandMark />
          <span className="version-pill">v0.1</span>
        </div>
        <div className="sidebar-content">
          <NavSection items={navigationItems} onNavigate={onClose} />
          <NavSection items={settingsItems} label="Workspace" onNavigate={onClose} />
        </div>
        <div className="sidebar-footer">
          <div className="foundation-card">
            <span className="status-dot" />
            <div>
              <strong>Foundation build</strong>
              <span>Learning engine online</span>
            </div>
          </div>
          <p className="sidebar-footnote">Build with focus. Practice with intent.</p>
        </div>
      </aside>
    </>
  );
}
