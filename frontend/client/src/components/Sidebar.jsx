import {
  Home,
  Map,
  TriangleAlert,
  Shield,
  FileText,
  Bell,
  Settings,
  LogOut,
  Thermometer,
  Wind,
  Droplets,
  Eye,
  ChevronRight,
} from "lucide-react";

const menuItems = [
  { label: "Dashboard", icon: Home, badge: null, active: true },
  { label: "Fire Map", icon: Map, badge: "7" },
  { label: "Alerts", icon: TriangleAlert, badge: "31" },
  { label: "Misinformation Review", icon: Shield, badge: "14" },
  { label: "Reports", icon: FileText, badge: null },
];

function InfoBox({ icon: Icon, title, value }) {
  return (
    <div className="info-box">
      <Icon size={16} />
      <span>{title}</span>
      <b>{value}</b>
    </div>
  );
}

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-logo">FF</div>
        <div>
          <h1>FireFusion</h1>
          <p>Emergency Operations</p>
        </div>
      </div>

      <p className="section-title">Main Menu</p>

      <nav className="nav-list">
        {menuItems.map((item) => {
          const Icon = item.icon;
          return (
            <button key={item.label} className={`nav-item ${item.active ? "active" : ""}`}>
              <span>
                <Icon size={17} />
                {item.label}
              </span>
              {item.badge && <b>{item.badge}</b>}
              {item.active && <ChevronRight size={16} />}
            </button>
          );
        })}
      </nav>

      <div className="ban-card">
        <h3><span></span>Total Fire Ban</h3>
        <p>No fires permitted</p>
        <small>Catastrophic conditions.</small>
      </div>

      <div className="weather-grid">
        <InfoBox icon={Thermometer} title="Temperature" value="42°C" />
        <InfoBox icon={Wind} title="Wind Speed" value="45 km/h" />
        <InfoBox icon={Droplets} title="Humidity" value="18%" />
        <InfoBox icon={Eye} title="Visibility" value="3 km" />
      </div>

      <p className="last-update">Last updated: 14:30</p>

      <div className="sidebar-bottom">
        <p className="section-title">System</p>

        <button className="nav-item">
          <span><Bell size={17} /> Notifications</span>
          <b>3</b>
        </button>

        <button className="nav-item">
          <span><Settings size={17} /> Settings</span>
        </button>

        <div className="profile-card">
          <div>JD</div>
          <span>
            <strong>Gaveesha Nuwansara</strong>
            <small>Emergency Manager</small>
          </span>
        </div>

        <button className="signout">
          <LogOut size={16} />
          Sign Out
        </button>

        <small className="version">
          Version 2.4.1<br />
          Last sync: 2 min ago
        </small>
      </div>
    </aside>
  );
}