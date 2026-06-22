import { useEffect, useState } from "react";
import { Shield, User, Users, AlertCircle } from "lucide-react";
import { api, User as UserType } from "@/api";
import { Spinner } from "@/components/Spinner";
import { EmptyState } from "@/components/EmptyState";
import { cn } from "@/lib/utils";

const roleStyles: Record<string, string> = {
  admin: "bg-[#1F2A44]/8 text-[#1F2A44] border-[#1F2A44]/20",
  cpa:   "bg-blue-50 text-blue-700 border-blue-200",
  client:"bg-zinc-50 text-zinc-600 border-zinc-200",
};

export function AdminUsersPage() {
  const [users, setUsers] = useState<UserType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.usersList()
      .then(setUsers)
      .catch(() => setError("Couldn't load users."))
      .finally(() => setLoading(false));
  }, []);

  const byRole = {
    admin:  users.filter((u) => u.role === "admin"),
    cpa:    users.filter((u) => u.role === "cpa"),
    client: users.filter((u) => u.role === "client"),
  };

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-[#16181D]">Users</h1>
        <p className="text-sm text-[#5B6270] mt-0.5">
          All users in your firm — {users.length} total
        </p>
      </div>

      {loading && (
        <div className="flex justify-center py-16">
          <Spinner className="h-5 w-5 text-[#5B6270]" />
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 text-sm text-rose-600 bg-rose-50 border border-rose-200 rounded-lg px-4 py-3">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {!loading && !error && users.length === 0 && (
        <EmptyState icon={<Users className="h-8 w-8" />} heading="No users" body="No users found in your firm." />
      )}

      {!loading && !error && (
        <div className="space-y-6">
          {(["admin", "cpa", "client"] as const).map((role) => {
            const group = byRole[role];
            if (group.length === 0) return null;
            return (
              <section key={role}>
                <h2 className="text-xs font-medium text-[#5B6270] uppercase tracking-wide mb-2 flex items-center gap-1.5">
                  {role === "admin" && <Shield className="h-3.5 w-3.5" />}
                  {role === "cpa" && <User className="h-3.5 w-3.5" />}
                  {role === "client" && <Users className="h-3.5 w-3.5" />}
                  {role === "admin" ? "Admins" : role === "cpa" ? "CPAs" : "Clients"}
                  <span className="text-[#5B6270]/60">({group.length})</span>
                </h2>
                <div className="space-y-2">
                  {group.map((user) => (
                    <div
                      key={user.id}
                      className="flex items-center gap-4 bg-white rounded-lg border border-[#E6E8EC] px-4 py-3 shadow-card"
                    >
                      <div className="w-8 h-8 rounded-full bg-[#1F2A44]/8 flex items-center justify-center shrink-0">
                        <span className="text-xs font-semibold text-[#1F2A44]">
                          {user.name.charAt(0).toUpperCase()}
                        </span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-[#16181D] truncate">{user.name}</p>
                        <p className="text-xs text-[#5B6270] truncate">{user.email}</p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {!user.is_active && (
                          <span className="text-xs text-rose-600 bg-rose-50 border border-rose-200 rounded-full px-2 py-0.5">
                            Inactive
                          </span>
                        )}
                        <span
                          className={cn(
                            "text-xs border rounded-full px-2.5 py-0.5 font-medium capitalize",
                            roleStyles[user.role]
                          )}
                        >
                          {user.role}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
