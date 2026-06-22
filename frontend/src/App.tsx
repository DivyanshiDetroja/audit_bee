import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "@/auth";
import { Spinner } from "@/components/Spinner";

import { LoginPage } from "@/pages/LoginPage";
import { RedeemPage } from "@/pages/RedeemPage";

import { CPAShell } from "@/pages/cpa/CPAShell";
import { ClientsPage } from "@/pages/cpa/ClientsPage";
import { ClientDetailPage } from "@/pages/cpa/ClientDetailPage";
import { ConnectionsPage as CPAConnectionsPage } from "@/pages/cpa/ConnectionsPage";

import { PortalShell } from "@/pages/portal/PortalShell";
import { PortalPage } from "@/pages/portal/PortalPage";

import { AdminShell } from "@/pages/admin/AdminShell";
import { AdminUsersPage } from "@/pages/admin/AdminUsersPage";
import { AssignmentsPage } from "@/pages/admin/AssignmentsPage";
import { AuditLogPage } from "@/pages/admin/AuditLogPage";
import { ConnectionsPage as AdminConnectionsPage } from "@/pages/cpa/ConnectionsPage";

function RoleRoot() {
  const { user, loading } = useAuth();
  if (loading) return <FullSpinner />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role === "admin") return <Navigate to="/admin/users" replace />;
  if (user.role === "cpa")   return <Navigate to="/cpa/clients" replace />;
  return <Navigate to="/portal" replace />;
}

function AuthedShell({
  role,
  children,
}: {
  role: "admin" | "cpa" | "client" | ("admin" | "cpa")[];
  children: React.ReactElement;
}) {
  const { user, loading } = useAuth();
  if (loading) return <FullSpinner />;
  if (!user) return <Navigate to="/login" replace />;
  const allowed = Array.isArray(role) ? role : [role];
  if (!allowed.includes(user.role as never)) return <Navigate to="/" replace />;
  return children;
}

function FullSpinner() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#F7F8FA]">
      <Spinner className="h-5 w-5 text-[#5B6270]" />
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/redeem" element={<RedeemPage />} />

      <Route path="/cpa" element={<AuthedShell role={["admin", "cpa"]}><CPAShell /></AuthedShell>}>
        <Route index element={<Navigate to="clients" replace />} />
        <Route path="clients" element={<ClientsPage />} />
        <Route path="clients/:clientId" element={<ClientDetailPage />} />
        <Route path="connections" element={<CPAConnectionsPage />} />
      </Route>

      <Route path="/portal" element={<AuthedShell role="client"><PortalShell /></AuthedShell>}>
        <Route index element={<PortalPage />} />
      </Route>

      <Route path="/admin" element={<AuthedShell role="admin"><AdminShell /></AuthedShell>}>
        <Route index element={<Navigate to="users" replace />} />
        <Route path="users" element={<AdminUsersPage />} />
        <Route path="assignments" element={<AssignmentsPage />} />
        <Route path="connections" element={<AdminConnectionsPage />} />
        <Route path="audit-log" element={<AuditLogPage />} />
      </Route>

      <Route path="/" element={<RoleRoot />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
