import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { Users, Link2, ScrollText, LogOut, UserCheck } from "lucide-react";
import { useAuth } from "@/auth";
import { cn } from "@/lib/utils";

const nav = [
  { to: "/admin/users",       label: "Users",       icon: Users },
  { to: "/admin/assignments", label: "Assignments", icon: UserCheck },
  { to: "/admin/connections", label: "Connections", icon: Link2 },
  { to: "/admin/audit-log",   label: "Audit Log",   icon: ScrollText },
];

export function AdminShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="flex h-screen overflow-hidden bg-[#F7F8FA]">
      <nav className="w-56 shrink-0 bg-[#1F2A44] flex flex-col" aria-label="Admin navigation">
        <div className="px-4 py-5 border-b border-white/10">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-md bg-[#3B6CF6] flex items-center justify-center shrink-0">
              <svg className="w-4 h-4 text-white" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h4a1 1 0 100-2H7z" clipRule="evenodd" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-semibold text-white leading-tight">Audit Bee</p>
              <p className="text-[10px] text-white/50 leading-tight">Admin</p>
            </div>
          </div>
        </div>
        <div className="flex-1 px-2 py-4 space-y-0.5">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-white/10 text-white font-medium"
                    : "text-white/60 hover:bg-white/5 hover:text-white"
                )
              }
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </NavLink>
          ))}
        </div>
        <div className="px-3 py-4 border-t border-white/10">
          <p className="text-xs text-white/50 truncate mb-0.5">{user?.name}</p>
          <p className="text-[10px] text-white/30 truncate mb-3">{user?.email}</p>
          <button
            onClick={() => { logout(); navigate("/login"); }}
            className="flex items-center gap-2 text-xs text-white/50 hover:text-white transition-colors"
          >
            <LogOut className="h-3.5 w-3.5" />
            Sign out
          </button>
        </div>
      </nav>
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
