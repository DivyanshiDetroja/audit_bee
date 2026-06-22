import { useEffect, useState, useCallback } from "react";
import { useAuth } from "@/auth";
import { api, Document, RequiredDocument } from "@/api";
import { DocumentCard } from "@/components/DocumentCard";
import { UploadZone } from "@/components/UploadZone";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { Spinner } from "@/components/Spinner";
import { FileText, Clock } from "lucide-react";

export function PortalPage() {
  const { user } = useAuth();
  const clientId = user?.client_id;

  const [docs, setDocs] = useState<Document[]>([]);
  const [checklist, setChecklist] = useState<RequiredDocument[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!clientId) return;
    const [d, c] = await Promise.all([
      api.clientDocuments(clientId),
      api.checklist(clientId),
    ]);
    setDocs(d.sort((a, b) =>
      new Date(b.uploaded_at).getTime() - new Date(a.uploaded_at).getTime()
    ));
    setChecklist(c);
    setLoading(false);
  }, [clientId]);

  useEffect(() => { load(); }, [load]);

  async function handleUpload(file: File) {
    if (!clientId) return;
    const doc = await api.uploadDocument(clientId, file);
    setDocs((prev) => [doc, ...prev]);
  }

  const pending = checklist.filter((i) => i.status === "pending");
  const received = checklist.filter((i) => i.status === "received");

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner className="h-5 w-5 text-[#5B6270]" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Greeting */}
      <div>
        <h1 className="text-xl font-semibold text-[#16181D]">
          Welcome, {user?.name?.split(" ")[0]}
        </h1>
        <p className="text-sm text-[#5B6270] mt-0.5">
          Upload your tax documents below. Your CPA will be notified automatically.
        </p>
      </div>

      {/* Pending checklist */}
      {pending.length > 0 && (
        <section>
          <div className="flex items-center gap-2 mb-3">
            <Clock className="h-4 w-4 text-amber-500" />
            <h2 className="text-sm font-medium text-[#16181D]">
              {pending.length} document{pending.length !== 1 ? "s" : ""} still needed
            </h2>
          </div>
          <div className="space-y-2">
            {pending.map((item) => (
              <div
                key={item.id}
                className="flex items-center gap-3 bg-white rounded-lg border border-[#E6E8EC] px-4 py-3"
              >
                <div className="w-2 h-2 rounded-full bg-amber-400 shrink-0" />
                <p className="flex-1 text-sm text-[#16181D]">{item.label}</p>
                <StatusBadge status="pending" />
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Upload zone */}
      <section>
        <h2 className="text-sm font-medium text-[#16181D] mb-3">Upload a document</h2>
        <UploadZone onUpload={handleUpload} />
      </section>

      {/* Document list */}
      <section>
        <h2 className="text-sm font-medium text-[#16181D] mb-3">
          {docs.length > 0 ? `Your documents (${docs.length})` : "Your documents"}
        </h2>
        {docs.length === 0 ? (
          <EmptyState
            icon={<FileText className="h-8 w-8" />}
            heading="No documents uploaded yet"
            body="Upload a document above — you'll see it here as it's read and classified."
          />
        ) : (
          <div className="space-y-3">
            {docs.map((doc) => (
              <DocumentCard
                key={doc.id}
                doc={doc}
                onUpdated={(updated) =>
                  setDocs((prev) =>
                    prev.map((d) => (d.id === updated.id ? updated : d))
                  )
                }
              />
            ))}
          </div>
        )}
      </section>

      {/* Received checklist */}
      {received.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-[#5B6270] mb-3">
            Received ({received.length})
          </h2>
          <div className="space-y-2">
            {received.map((item) => (
              <div
                key={item.id}
                className="flex items-center gap-3 bg-[#F7F8FA] rounded-lg border border-[#E6E8EC] px-4 py-3"
              >
                <div className="w-2 h-2 rounded-full bg-green-500 shrink-0" />
                <p className="flex-1 text-sm text-[#5B6270]">{item.label}</p>
                <StatusBadge status="received" />
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
