import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Building2, User, ChevronRight, AlertCircle } from "lucide-react";
import { api, Client } from "@/api";
import { EmptyState } from "@/components/EmptyState";
import { Spinner } from "@/components/Spinner";

export function ClientsPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.clients()
      .then(setClients)
      .catch(() => setError("Couldn't load clients. Check your connection."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-[#16181D]">Your Clients</h1>
        <p className="text-sm text-[#5B6270] mt-0.5">
          {clients.length > 0
            ? `${clients.length} client${clients.length !== 1 ? "s" : ""} assigned to you`
            : "Clients assigned to you appear here"}
        </p>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-16">
          <Spinner className="h-5 w-5 text-[#5B6270]" />
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 text-sm text-rose-600 bg-rose-50 border border-rose-200 rounded-lg px-4 py-3">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {!loading && !error && clients.length === 0 && (
        <EmptyState
          icon={<User className="h-8 w-8" />}
          heading="No clients yet"
          body="Clients assigned to you by an admin will appear here."
        />
      )}

      {!loading && !error && clients.length > 0 && (
        <div className="space-y-2">
          {clients.map((client) => (
            <ClientRow key={client.id} client={client} />
          ))}
        </div>
      )}
    </div>
  );
}

function ClientRow({ client }: { client: Client }) {
  const Icon = client.type === "business" ? Building2 : User;

  return (
    <Link
      to={`/cpa/clients/${client.id}`}
      className="flex items-center gap-4 bg-white rounded-lg border border-[#E6E8EC] px-4 py-3.5 shadow-card hover:shadow-card-hover hover:border-[#3B6CF6]/30 transition-all group"
    >
      <div className="w-9 h-9 rounded-lg bg-[#F7F8FA] border border-[#E6E8EC] flex items-center justify-center shrink-0">
        <Icon className="h-4 w-4 text-[#5B6270]" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-[#16181D] truncate">{client.name}</p>
        <p className="text-xs text-[#5B6270] mt-0.5 capitalize">{client.type}</p>
      </div>
      {client.pending_count > 0 && (
        <span className="shrink-0 inline-flex items-center rounded-full bg-amber-50 border border-amber-200 px-2 py-0.5 text-xs font-medium text-amber-700">
          {client.pending_count} pending
        </span>
      )}
      <ChevronRight className="h-4 w-4 text-[#5B6270] group-hover:text-[#3B6CF6] transition-colors shrink-0" />
    </Link>
  );
}
