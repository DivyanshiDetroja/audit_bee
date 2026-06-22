import { useEffect, useState } from "react";
import { ScrollText, AlertCircle } from "lucide-react";
import { api, AuditLog } from "@/api";
import { Spinner } from "@/components/Spinner";
import { EmptyState } from "@/components/EmptyState";

const ACTION_LABELS: Record<string, string> = {
  document_upload:          "Document uploaded",
  document_upload_email_sim:"Document uploaded (email sim)",
  document_list:            "Documents listed",
  document_view:            "Document viewed",
  document_download:        "Document downloaded",
  probe_answered:           "Probe answered",
  reminder_drafted:         "Reminder drafted",
  reminder_sent:            "Reminder sent",
  integration_toggled:      "Integration toggled",
  login:                    "Login",
};

export function AuditLogPage() {
  const [entries, setEntries] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.auditLog()
      .then(setEntries)
      .catch(() => setError("Couldn't load audit log."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-[#16181D]">Audit Log</h1>
        <p className="text-sm text-[#5B6270] mt-0.5">
          Every access and mutation — append-only, immutable.
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

      {!loading && !error && entries.length === 0 && (
        <EmptyState
          icon={<ScrollText className="h-8 w-8" />}
          heading="Audit log is empty"
          body="Actions taken by any user in your firm appear here."
        />
      )}

      {!loading && !error && entries.length > 0 && (
        <div className="bg-white rounded-lg border border-[#E6E8EC] shadow-card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#E6E8EC] bg-[#F7F8FA]">
                <th className="text-left px-4 py-2.5 text-xs font-medium text-[#5B6270]">When</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-[#5B6270]">Action</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-[#5B6270] hidden md:table-cell">Resource</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-[#5B6270] hidden lg:table-cell">IP</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E6E8EC]">
              {entries.map((entry) => (
                <tr key={entry.id} className="hover:bg-[#F7F8FA] transition-colors">
                  <td className="px-4 py-2.5 font-mono text-xs text-[#5B6270] whitespace-nowrap">
                    {new Date(entry.created_at).toLocaleDateString("en-US", {
                      month: "short", day: "numeric",
                      hour: "2-digit", minute: "2-digit", second: "2-digit",
                    })}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className="text-xs font-medium text-[#16181D]">
                      {ACTION_LABELS[entry.action] ?? entry.action}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 hidden md:table-cell">
                    <span className="font-mono text-[10px] text-[#5B6270]">
                      {entry.resource_type}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 hidden lg:table-cell">
                    <span className="font-mono text-[10px] text-[#5B6270]">
                      {entry.ip ?? "—"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
