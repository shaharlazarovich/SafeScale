import { Routes, Route } from "react-router-dom";
import Layout from "@/components/layout/Layout";
import Dashboard from "@/pages/Dashboard";
import AccountsPage from "@/pages/AccountsPage";
import ConnectAccountPage from "@/pages/ConnectAccountPage";
import ScanDetailPage from "@/pages/ScanDetailPage";
import ScanResourcesPage from "@/pages/ScanResourcesPage";
import AuditLogPage from "@/pages/AuditLogPage";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/accounts" element={<AccountsPage />} />
        <Route path="/accounts/connect" element={<ConnectAccountPage />} />
        <Route path="/scans/:id" element={<ScanDetailPage />} />
        <Route path="/scans/:id/resources" element={<ScanResourcesPage />} />
        <Route path="/scans/:id/log" element={<AuditLogPage />} />
      </Routes>
    </Layout>
  );
}
