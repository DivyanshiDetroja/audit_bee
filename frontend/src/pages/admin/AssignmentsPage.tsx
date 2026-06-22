import { useEffect, useState } from "react";
import { Building2, User, AlertCircle, CheckCircle2 } from "lucide-react";
import { api, Client, User as UserType } from "@/api";
import { Spinner } from "@/components/Spinner";
import { EmptyState } from "@/components/EmptyState";
import { cn } from "@/lib/utils";

export function AssignmentsPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [cpas, setCpas] = useState<UserType[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.clients(), api.usersList()])
      .then(([c, u]) => {
        setClients(c);
        setCpas(u.filter((u) => u.role === "cpa"));
      })
      .catch(() => setError("Couldn't load data."))
      .finally(() => setLoading(false));
  }, []);

  async function handleAssign(clientId: string, cpaId: string) {
    setSaving(clientId);
    setError(null);
    try {
      const updated = await api.assignCPA(clientId, cpaId || null);
      setClients((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      setSaved(clientId);
      setTimeout(() => setSaved((s) => (s === clientId ? null : s)), 2000);
    } catch {
      setError("Couldn't update assignment. Try again.");
    } finally {
      setSaving(null);
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-[#16181D]">Assignments</h1>
        <p className="text-sm text-[#5B6270] mt-0.5">
          Assign clients to CPAs. Each client can have one assigned CPA.
        </p>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-sm text-rose-600 bg-rose-50 border border-rose-200 rounded-lg px-4 py-3 mb-4">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-16">
          <Spinner className="h-5 w-5 text-[#5B6270]" />
        </div>
      ) : clients.length === 0 ? (
        <EmptyState
          icon={<User className="h-8 w-8" />}
          heading="No clients yet"
          body="Clients appear here once they are added to the firm."
        />
      ) : (
        <div className="space-y-2">
          {clients.map((client) => {
            const Icon = client.type === "business" ? Building2 : User;
            const isSaving = saving === client.id;
            const isSaved = saved === client.id;

            return (
              <div
                key={client.id}
                className="flex items-center gap-4 bg-white rounded-lg border border-[#E6E8EC] px-4 py-3.5 shadow-card"
              >
                <div className="w-9 h-9 rounded-lg bg-[#F7F8FA] border border-[#E6E8EC] flex items-center justify-center shrink-0">
                  <Icon className="h-4 w-4 text-[#5B6270]" />
                </div>

                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-[#16181D] truncate">{client.name}</p>
                  <p className="text-xs text-[#5B6270] capitalize">{client.type}</p>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {isSaved && (
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                  )}
                  {isSaving ? (
                    <Spinner className="h-4 w-4 text-[#5B6270]" />
                  ) : (
                    <select
                      value={client.assigned_cpa_id ?? ""}
                      onChange={(e) => handleAssign(client.id, e.target.value)}
                      className={cn(
                        "rounded-md border border-[#E6E8EC] bg-white px-3 py-1.5 text-sm text-[#16181D]",
                        "focus:outline-none focus:ring-2 focus:ring-[#3B6CF6] focus:border-transparent",
                        "min-w-[180px]"
                      )}
                    >
                      <option value="">— Unassigned —</option>
                      {cpas.map((cpa) => (
                        <option key={cpa.id} value={String(cpa.id)}>
                          {cpa.name}
                        </option>
                      ))}
                    </select>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
