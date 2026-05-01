import {
  Truck,
  Users,
  Droplets,
  ArrowLeft,
  ArrowRight,
} from "lucide-react";

import Layout from "../components/Layout";
import "../App.css";

const adviceCards = [
  {
    title: "ABC Radio Internet & Guide",
    text: "Stay informed with official emergency broadcasts from ABC Radio.",
    image:
      "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=800&q=80",
  },
  {
    title: "Find emergency services near you",
    text: "Locate nearby stations, hospitals, and evacuation services.",
    image:
      "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=800&q=80",
  },
  {
    title: "Your mobile phone could help save your life",
    text: "Enable emergency alerts and location services for critical warnings.",
    image:
      "https://images.unsplash.com/photo-1516321497487-e288fb19713f?auto=format&fit=crop&w=800&q=80",
  },
  {
    title: "Helping you recover after an emergency",
    text: "Access support resources, financial help, and community services.",
    image:
      "https://images.unsplash.com/photo-1521791055366-0d553872125f?auto=format&fit=crop&w=800&q=80",
  },
];

export default function Dashboard() {
  return (
    <Layout title="Dashboard">
      <section className="stats-grid">
        <Stat title="Overall Bushfire Risk" value="EXTREME" note="Critical conditions" danger />
        <Stat title="Active Fire Zones" value="7" note="+2 since 12:00" />
        <Stat title="Misinformation Alerts" value="14" note="8 pending review" purple />
        <Stat title="Communities at Risk" value="23" note="Population: ~12,400" />
        <Stat title="Official Alerts Issued" value="31" note="Last 6 hours" blue />
      </section>

      <section className="content-grid">
        <div className="panel updates">
          <h3>Latest Official Updates</h3>

          <UpdateCard
            agency="CFA"
            time="8 min ago"
            title="East Gippsland Fire Warning Upgraded"
            text="Emergency Warning issued for communities in East Gippsland. Leave immediately if safe to do so."
            type="CRITICAL"
            color="red"
          />

          <UpdateCard
            agency="VicEmergency"
            time="25 min ago"
            title="Total Fire Ban Declared"
            text="Total Fire Ban in effect for Central, North Central, and Mallee districts until 11:59 PM."
            type="WARNING"
            color="orange"
          />
        </div>

        <div className="panel incident">
          <h3>Incident Overview</h3>

          <div className="risk-line">
            <span>Current Risk Level</span>
            <b>EXTREME</b>
          </div>

          <div className="bar">
            <span></span>
          </div>

          <div className="mini-grid">
            <Mini title="Wind Speed" value="45 km/h NW" />
            <Mini title="Temperature" value="41°C" />
            <Mini title="Humidity" value="12%" />
            <Mini title="Evacuation Status" value="Active (7 zones)" />
          </div>

          <div className="slider">
            <button>
              <ArrowLeft size={22} />
            </button>

            <div>
              <img
                src="https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=800&q=80"
                alt="Home fire prevention"
              />
              <strong>Home fire prevention</strong>
            </div>

            <button>
              <ArrowRight size={22} />
            </button>
          </div>
        </div>

        <div className="panel resources">
          <div className="panel-head">
            <h3>Resource Allocation</h3>
            <a>Manage</a>
          </div>

          <Resource icon={Truck} name="Fire Trucks" value="45 deployed / 23 available" percent="65%" status="orange" />
          <Resource icon={Users} name="Personnel" value="312 deployed / 156 available" percent="67%" status="orange" />
          <Resource icon={Droplets} name="Water Bombers" value="8 deployed / 3 available" percent="73%" status="red" />
          <Resource icon={Truck} name="Water Tankers" value="28 deployed / 15 available" percent="65%" status="green" />

          <div className="legend">
            <span><i className="green"></i>Optimal</span>
            <span><i className="orange"></i>Stretched</span>
            <span><i className="red"></i>Critical</span>
          </div>
        </div>
      </section>

      <section>
        <h3 className="advice-title">Emergency Advice</h3>

        <div className="advice-grid">
          {adviceCards.map((card) => (
            <article className="advice-card" key={card.title}>
              <img src={card.image} alt={card.title} />
              <div>
                <h4>{card.title}</h4>
                <p>{card.text}</p>
              </div>
            </article>
          ))}
        </div>
      </section>
    </Layout>
  );
}

function Stat({ title, value, note, danger, purple, blue }) {
  return (
    <div className="stat-card">
      <p>{title}</p>
      <h3 className={danger ? "danger" : purple ? "purple" : blue ? "blue" : ""}>
        {value}
      </h3>
      <span>{note}</span>
    </div>
  );
}

function UpdateCard({ agency, time, title, text, type, color }) {
  return (
    <article className={`update-card ${color}`}>
      <div>
        <strong>{agency}</strong>
        <span>{time}</span>
      </div>
      <h4>{title}</h4>
      <p>{text}</p>
      <b>{type}</b>
    </article>
  );
}

function Mini({ title, value }) {
  return (
    <div className="mini-card">
      <strong>{title}</strong>
      <p>{value}</p>
    </div>
  );
}

function Resource({ icon: Icon, name, value, percent, status }) {
  return (
    <div className="resource">
      <div>
        <span>
          <Icon size={15} />
          {name}
        </span>
        <p>{value}</p>
      </div>

      <div className="resource-bar">
        <span className={status} style={{ width: percent }}></span>
      </div>

      <small>{percent} deployed</small>
    </div>
  );
}