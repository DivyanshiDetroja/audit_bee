import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Mail, FileSignature, Calendar, BarChart3, AlertCircle, CheckCircle2 } from "lucide-react";
import { api, Integration, Client } from "@/api";
import { StatusBadge } from "@/components/StatusBadge";
import { UploadZone } from "@/components/UploadZone";
import { Spinner } from "@/components/Spinner";
import { useAuth } from "@/auth";

const INTEGRATION_META: Record<string, { icon: React.ElementType; description: string }> = {
  Gmail:      { icon: Mail,          description: "Receive documents via inbound email threads" },
  DocuSign:   { icon: FileSignature, description: "Send and track engagement letters for e-signature" },
  Calendly:   { icon: Calendar,      description: "Schedule client review meetings automatically" },
  QuickBooks: { icon: BarChart3,     description: "Sync financial summaries and prior-year data" },
};

export function ConnectionsPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Simulate email state
  const [simClientId, setSimClientId] = useState<string>("");
  const [simulating, setSimulating] = useState(false);
  const [simSuccess, setSimSuccess] = useState<string | null>(null);
  const [simError, setSimError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.integrations(), api.clients()])
      .then(([ints, cls]) => {
        setIntegrations(ints);
        setClients(cls);
        if (cls.length > 0) setSimClientId(cls[0].id);
      })
      .finally(() => setLoading(false));
  }, []);

  async function handleToggle(id: string) {
    setToggling(id);
    setError(null);
    try {
      const updated = await api.toggleIntegration(id);
      setIntegrations((prev) => prev.map((i) => (i.id === updated.id ? updated : i)));
    } catch {
      setError("Couldn't update connection. Try again.");
    } finally {
      setToggling(null);
    }
  }

  async function handleSimulateEmail(file: File) {
    if (!simClientId) return;
    setSimulating(true);
    setSimError(null);
    setSimSuccess(null);
    try {
      await api.simulateEmail(simClientId, file, "inbound@gmail.example.com");
      const client = clients.find((c) => c.id === simClientId);
      setSimSuccess(simClientId);
      setTimeout(() => {
        navigate(`/cpa/clients/${simClientId}`);
      }, 1200);
      void client;
    } catch {
      setSimError("Simulation failed. Try again.");
    } finally {
      setSimulating(false);
    }
  }

  const gmailConnected = integrations.find((i) => i.name === "Gmail")?.status === "connected";

  return (
    <div className="max-w-2xl mx-auto px-6 py-8">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-[#16181D]">Connections</h1>
        <p className="text-sm text-[#5B6270] mt-0.5">
          Integrations that feed documents into the Audit Bee pipeline.
          {user?.role !== "admin" && " Contact your admin to change connection status."}
        </p>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-sm text-rose-600 bg-rose-50 border border-rose-200 rounded-lg px-4 py-3 mb-4">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12">
          <Spinner className="h-5 w-5 text-[#5B6270]" />
        </div>
      ) : (
        <>
          <div className="space-y-3">
            {integrations.map((integration) => {
              const meta = INTEGRATION_META[integration.name];
              const Icon = meta?.icon ?? Mail;
              return (
                <div
                  key={integration.id}
                  className="bg-white rounded-lg border border-[#E6E8EC] shadow-card px-5 py-4 flex items-center gap-4"
                >
                  <div className="w-10 h-10 rounded-lg bg-[#F7F8FA] border border-[#E6E8EC] flex items-center justify-center shrink-0">
                    <Icon className="h-5 w-5 text-[#1F2A44]" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <p className="text-sm font-medium text-[#16181D]">{integration.name}</p>
                      <StatusBadge status={integration.status} />
                    </div>
                    <p className="text-xs text-[#5B6270]">
                      {meta?.description ?? "Integration"}
                    </p>
                    {integration.connected_at && integration.status === "connected" && (
                      <p className="text-[10px] font-mono text-[#5B6270] mt-0.5">
                        Connected{" "}
                        {new Date(integration.connected_at).toLocaleDateString("en-US", {
                          month: "short", day: "numeric", year: "numeric",
                        })}
                      </p>
                    )}
                  </div>
                  {user?.role === "admin" && (
                    <button
                      onClick={() => handleToggle(integration.id)}
                      disabled={toggling === integration.id}
                      className="shrink-0 text-xs font-medium text-[#5B6270] hover:text-[#16181D] border border-[#E6E8EC] rounded-md px-3 py-1.5 hover:border-[#16181D] transition-colors disabled:opacity-50"
                    >
                      {toggling === integration.id ? (
                        <Spinner className="h-3.5 w-3.5" />
                      ) : integration.status === "connected" ? (
                        "Disconnect"
                      ) : (
                        "Connect"
                      )}
                    </button>
                  )}
                </div>
              );
            })}
          </div>

          {/* Simulate inbound email — the demo moment */}
          <div className="mt-8 bg-white rounded-lg border border-[#E6E8EC] shadow-card overflow-hidden">
            <div className="px-5 py-3.5 border-b border-[#E6E8EC] flex items-center gap-3">
              <Mail className="h-4 w-4 text-[#5B6270]" />
              <div>
                <p className="text-sm font-medium text-[#16181D]">Simulate inbound email</p>
                <p className="text-xs text-[#5B6270]">
                  Drop a document as if it arrived via{" "}
                  {gmailConnected ? "Gmail" : "email"} — runs the same classification pipeline.
                </p>
              </div>
            </div>
            <div className="px-5 py-4 space-y-3">
              {clients.length > 1 && (
                <div>
                  <label className="block text-xs font-medium text-[#5B6270] mb-1.5">
                    Route to client
                  </label>
                  <select
                    value={simClientId}
                    onChange={(e) => {
                      setSimClientId(e.target.value);
                      setSimSuccess(null);
                      setSimError(null);
                    }}
                    className="rounded-md border border-[#E6E8EC] bg-white px-3 py-1.5 text-sm text-[#16181D] focus:outline-none focus:ring-2 focus:ring-[#3B6CF6] focus:border-transparent"
                  >
                    {clients.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </div>
              )}

              {simulating ? (
                <div className="flex items-center gap-2 text-sm text-[#5B6270] py-2">
                  <Spinner className="h-4 w-4" />
                  Sending to pipeline…
                </div>
              ) : simSuccess ? (
                <div className="flex items-center gap-2 text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-4 py-3">
                  <CheckCircle2 className="h-4 w-4 shrink-0" />
                  Document received — redirecting to client…
                </div>
              ) : (
                <>
                  <UploadZone
                    onUpload={handleSimulateEmail}
                    label="Drop attachment to simulate email"
                  />
                  {simError && (
                    <p className="flex items-center gap-1.5 text-xs text-rose-600">
                      <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                      {simError}
                    </p>
                  )}
                </>
              )}
            </div>
          </div>

          <p className="mt-4 text-xs text-[#5B6270] bg-[#F7F8FA] border border-[#E6E8EC] rounded-lg px-4 py-3">
            <strong>Demo note:</strong> These connections are simulated. In production, each would redirect
            through OAuth and receive live webhooks. All channels feed the same classification pipeline.
          </p>
        </>
      )}
    </div>
  );
}
