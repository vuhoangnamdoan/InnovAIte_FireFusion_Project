import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import Footer from "./Footer";

export default function Layout({ children, title = "Dashboard" }) {
  return (
    <div className="dashboard-shell">
      <Sidebar />

      <main className="main">
        <Topbar title={title} />
        {children}
        <Footer />
      </main>
    </div>
  );
}