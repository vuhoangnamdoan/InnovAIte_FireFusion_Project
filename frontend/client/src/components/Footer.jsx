function FooterCol({ title, links }) {
  return (
    <div>
      <h4>{title}</h4>
      {links.map((link) => (
        <p key={link}>{link}</p>
      ))}
    </div>
  );
}

export default function Footer() {
  return (
    <footer className="footer">
      <FooterCol
        title="About FireFusion"
        links={[
          "AI-driven bushfire forecasting and misinformation monitoring.",
          "Project Overview",
          "Mission & Vision",
          "Integrated Dashboard",
        ]}
      />

      <FooterCol
        title="Core Features"
        links={[
          "Bushfire Forecasting",
          "Misinformation Detection",
          "Human Review Workflow",
          "Risk Visualisation",
        ]}
      />

      <FooterCol
        title="Data & Resources"
        links={[
          "Weather & Fire Data",
          "Historical Fire Cases",
          "Social Media Analysis",
          "Documentation",
        ]}
      />

      <FooterCol
        title="Connect With Us"
        links={["Email", "LinkedIn", "Teams / Project Updates"]}
      />
    </footer>
  );
}
