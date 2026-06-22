import { useEffect, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ArrowLeft, FileText, Clock, MessageSquare, BrainCircuit,
  Mail, AlertCircle, Building2, User, Upload, Send, UserPlus, Copy, CheckCheck
} from "lucide-react";
import {
  api, Client, Document, RequiredDocument,
  ContextEntry, ContextProbe, Reminder
} from "@/api";
import { DocumentCard } from "@/components/DocumentCard";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { Spinner } from "@/components/Spinner";
import { UploadZone } from "@/components/UploadZone";
import { cn } from "@/lib/utils";

type Tab = "documents" | "pending" | "context" | "probes" | "reminders";

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: "documents", label: "Documents", icon: FileText },
  { id: "pending",   label: "Pending",   icon: Clock },
  { id: "context",   label: "Context",   icon: MessageSquare },
  { id: "probes",    label: "Probes",    icon: BrainCircuit },
  { id: "reminders", label: "Reminders", icon: Mail },
];

export function ClientDetailPage() {
  const { clientId } = useParams<{ clientId: string }>();
  const [client, setClient] = useState<Client | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("documents");
  const [loading, setLoading] = useState(true);

  // Invite modal state
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteLink, setInviteLink] = useState<string | null>(null);
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [inviteCopied, setInviteCopied] = useState(false);

  async function handleInvite() {
    if (!clientId || !inviteEmail.trim()) return;
    setInviteLoading(true);
    setInviteError(null);
    try {
      const { invite_token } = await api.inviteClient(clientId, inviteEmail.trim());
      setInviteLink(`${window.location.origin}/redeem?token=${invite_token}`);
    } catch (e: unknown) {
      setInviteError(e instanceof Error ? e.message : "Failed to generate invite");
    } finally {
      setInviteLoading(false);
    }
  }

  function handleCopy() {
    if (!inviteLink) return;
    navigator.clipboard.writeText(inviteLink);
    setInviteCopied(true);
    setTimeout(() => setInviteCopied(false), 2000);
  }

  function closeInvite() {
    setInviteOpen(false);
    setInviteEmail("");
    setInviteLink(null);
    setInviteError(null);
    setInviteCopied(false);
  }

  useEffect(() => {
    if (!clientId) return;
    setLoading(true);
    api.client(clientId)
      .then(setClient)
      .finally(() => setLoading(false));
  }, [clientId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-5 w-5 text-[#5B6270]" />
      </div>
    );
  }

  if (!client) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-8">
        <p className="text-sm text-rose-600">Client not found.</p>
      </div>
    );
  }

  const Icon = client.type === "business" ? Building2 : User;

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      {/* Back */}
      <Link
        to="/cpa/clients"
        className="inline-flex items-center gap-1.5 text-xs text-[#5B6270] hover:text-[#16181D] mb-5 transition-colors"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        All clients
      </Link>

      {/* Client header */}
      <div className="flex items-center gap-4 mb-6">
        <div className="w-11 h-11 rounded-xl bg-[#1F2A44]/8 border border-[#E6E8EC] flex items-center justify-center shrink-0">
          <Icon className="h-5 w-5 text-[#1F2A44]" />
        </div>
        <div className="flex-1">
          <h1 className="text-xl font-semibold text-[#16181D]">{client.name}</h1>
          <p className="text-sm text-[#5B6270] capitalize">{client.type}</p>
        </div>
        <button
          onClick={() => setInviteOpen(true)}
          className="flex items-center gap-1.5 rounded-md border border-[#E6E8EC] bg-white px-3 py-1.5 text-sm text-[#5B6270] hover:text-[#16181D] hover:border-[#3B6CF6] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#3B6CF6]"
        >
          <UserPlus className="h-3.5 w-3.5" />
          Invite client
        </button>
      </div>

      {/* Invite modal */}
      {inviteOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          role="dialog"
          aria-modal="true"
          aria-label="Invite client"
          onClick={(e) => { if (e.target === e.currentTarget) closeInvite(); }}
        >
          <div className="bg-white rounded-xl shadow-xl border border-[#E6E8EC] w-full max-w-md mx-4 p-6">
            <h2 className="text-base font-semibold text-[#16181D] mb-1">Invite {client.name}</h2>
            <p className="text-sm text-[#5B6270] mb-4">
              Enter the client{"'"}s email to generate a one-time invite link.
            </p>

            {!inviteLink ? (
              <>
                <label className="block text-xs font-medium text-[#16181D] mb-1.5">
                  Client email
                </label>
                <input
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") handleInvite(); }}
                  placeholder="client@example.com"
                  className="w-full rounded-md border border-[#E6E8EC] px-3 py-2 text-sm text-[#16181D] placeholder:text-[#A0A6B3] focus:outline-none focus:ring-2 focus:ring-[#3B6CF6] focus:border-transparent mb-3"
                  autoFocus
                />
                {inviteError && (
                  <p className="flex items-center gap-1.5 text-xs text-rose-600 mb-3">
                    <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                    {inviteError}
                  </p>
                )}
                <div className="flex justify-end gap-2">
                  <button
                    onClick={closeInvite}
                    className="px-3 py-1.5 rounded-md text-sm text-[#5B6270] hover:text-[#16181D] transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleInvite}
                    disabled={inviteLoading || !inviteEmail.trim()}
                    className="flex items-center gap-1.5 px-4 py-1.5 rounded-md bg-[#3B6CF6] text-white text-sm font-medium hover:bg-[#2f5ed4] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {inviteLoading ? <Spinner className="h-3.5 w-3.5 text-white" /> : null}
                    Generate link
                  </button>
                </div>
              </>
            ) : (
              <>
                <p className="text-xs text-[#5B6270] mb-2">Share this link with the client:</p>
                <div className="flex items-center gap-2 bg-[#F7F8FA] border border-[#E6E8EC] rounded-md px-3 py-2 mb-4">
                  <span className="flex-1 text-xs font-mono text-[#16181D] break-all">{inviteLink}</span>
                  <button
                    onClick={handleCopy}
                    className="shrink-0 text-[#5B6270] hover:text-[#3B6CF6] transition-colors"
                    aria-label="Copy invite link"
                  >
                    {inviteCopied ? <CheckCheck className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
                  </button>
                </div>
                <div className="flex justify-end">
                  <button
                    onClick={closeInvite}
                    className="px-4 py-1.5 rounded-md bg-[#1F2A44] text-white text-sm font-medium hover:bg-[#16213a] transition-colors"
                  >
                    Done
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-[#E6E8EC] mb-6">
        <div className="flex gap-1 -mb-px overflow-x-auto">
          {TABS.map(({ id, label, icon: TabIcon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={cn(
                "flex items-center gap-1.5 px-3 py-2.5 text-sm border-b-2 whitespace-nowrap transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#3B6CF6] rounded-t",
                activeTab === id
                  ? "border-[#3B6CF6] text-[#3B6CF6] font-medium"
                  : "border-transparent text-[#5B6270] hover:text-[#16181D]"
              )}
            >
              <TabIcon className="h-3.5 w-3.5" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab panels */}
      {activeTab === "documents" && <DocumentsTab clientId={client.id} />}
      {activeTab === "pending"   && <PendingTab   clientId={client.id} />}
      {activeTab === "context"   && <ContextTab   clientId={client.id} />}
      {activeTab === "probes"    && <ProbesTab    clientId={client.id} />}
      {activeTab === "reminders" && <RemindersTab clientId={client.id} />}
    </div>
  );
}

// ── Documents tab ─────────────────────────────────────────────────────────────

function DocumentsTab({ clientId }: { clientId: string }) {
  const [docs, setDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    api.clientDocuments(clientId)
      .then((d) => setDocs(d.sort((a, b) =>
        new Date(b.uploaded_at).getTime() - new Date(a.uploaded_at).getTime()
      )))
      .finally(() => setLoading(false));
  }, [clientId]);

  useEffect(() => { load(); }, [load]);

  async function handleUpload(file: File) {
    const doc = await api.uploadDocument(clientId, file);
    setDocs((prev) => [doc, ...prev]);
  }

  async function handleSimulateEmail(file: File) {
    const doc = await api.simulateEmail(clientId, file, "client@email.example.com");
    setDocs((prev) => [doc, ...prev]);
  }

  if (loading) return <TabLoading />;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <p className="text-xs font-medium text-[#5B6270] mb-2 uppercase tracking-wide">Upload via portal</p>
          <UploadZone onUpload={handleUpload} />
        </div>
        <div>
          <p className="text-xs font-medium text-[#5B6270] mb-2 uppercase tracking-wide flex items-center gap-1">
            <Upload className="h-3 w-3" />
            Simulate inbound email
          </p>
          <UploadZone
            onUpload={handleSimulateEmail}
            label="Simulate email attachment"
          />
        </div>
      </div>

      {docs.length === 0 ? (
        <EmptyState
          icon={<FileText className="h-8 w-8" />}
          heading="No documents yet"
          body="Upload a document above — it will be read, classified, and filed automatically."
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
    </div>
  );
}

// ── Pending tab ───────────────────────────────────────────────────────────────

function PendingTab({ clientId }: { clientId: string }) {
  const [items, setItems] = useState<RequiredDocument[]>([]);
  const [all, setAll] = useState<RequiredDocument[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.pending(clientId), api.checklist(clientId)])
      .then(([p, a]) => { setItems(p); setAll(a); })
      .finally(() => setLoading(false));
  }, [clientId]);

  if (loading) return <TabLoading />;

  const received = all.filter((i) => i.status === "received");

  return (
    <div className="space-y-6">
      {items.length > 0 && (
        <section>
          <h2 className="text-xs font-medium text-[#5B6270] uppercase tracking-wide mb-3">
            Still needed ({items.length})
          </h2>
          <div className="space-y-2">
            {items.map((item) => (
              <ChecklistRow key={item.id} item={item} />
            ))}
          </div>
        </section>
      )}

      {received.length > 0 && (
        <section>
          <h2 className="text-xs font-medium text-[#5B6270] uppercase tracking-wide mb-3">
            Received ({received.length})
          </h2>
          <div className="space-y-2">
            {received.map((item) => (
              <ChecklistRow key={item.id} item={item} />
            ))}
          </div>
        </section>
      )}

      {all.length === 0 && (
        <EmptyState
          icon={<Clock className="h-8 w-8" />}
          heading="No checklist yet"
          body="The checklist is seeded automatically when documents are processed."
        />
      )}
    </div>
  );
}

function ChecklistRow({ item }: { item: RequiredDocument }) {
  return (
    <div className="flex items-center gap-3 bg-white rounded-lg border border-[#E6E8EC] px-4 py-3">
      <div
        className={cn(
          "w-2 h-2 rounded-full shrink-0",
          item.status === "received" ? "bg-green-500" : "bg-amber-400"
        )}
      />
      <p className="flex-1 text-sm text-[#16181D]">{item.label}</p>
      <StatusBadge status={item.status} />
    </div>
  );
}

// ── Context tab ───────────────────────────────────────────────────────────────

function ContextTab({ clientId }: { clientId: string }) {
  const [entries, setEntries] = useState<ContextEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.context(clientId).then(setEntries).finally(() => setLoading(false));
  }, [clientId]);

  if (loading) return <TabLoading />;

  if (entries.length === 0) {
    return (
      <EmptyState
        icon={<MessageSquare className="h-8 w-8" />}
        heading="No context yet"
        body="Context builds automatically as documents are classified and probes are answered."
      />
    );
  }

  const sourceLabel: Record<string, string> = {
    document: "Document",
    cpa_note: "CPA note",
    probe_answer: "Probe answer",
  };

  return (
    <div className="relative pl-5 space-y-0">
      <div className="absolute left-2 top-1 bottom-0 w-px bg-[#E6E8EC]" />
      {entries.map((entry) => (
        <div key={entry.id} className="relative pb-5">
          <div className="absolute -left-3 top-1 w-2.5 h-2.5 rounded-full border-2 border-[#E6E8EC] bg-white" />
          <div className="bg-white rounded-lg border border-[#E6E8EC] p-4 shadow-card">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-medium uppercase tracking-wide text-[#5B6270]">
                {sourceLabel[entry.source] ?? entry.source}
              </span>
              <span className="text-[10px] text-[#5B6270]">
                {new Date(entry.created_at).toLocaleDateString("en-US", {
                  month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                })}
              </span>
            </div>
            <p className="text-sm text-[#16181D] leading-relaxed">{entry.content}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Probes tab ────────────────────────────────────────────────────────────────

function ProbesTab({ clientId }: { clientId: string }) {
  const [probes, setProbes] = useState<ContextProbe[]>([]);
  const [loading, setLoading] = useState(true);
  const [answering, setAnswering] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});

  useEffect(() => {
    api.probes(clientId).then(setProbes).finally(() => setLoading(false));
  }, [clientId]);

  async function handleAnswer(probe: ContextProbe) {
    const answer = answers[probe.id];
    if (!answer?.trim()) return;
    setAnswering(probe.id);
    try {
      const updated = await api.answerProbe(clientId, probe.id, answer);
      setProbes((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
      setAnswers((prev) => { const n = { ...prev }; delete n[probe.id]; return n; });
    } finally {
      setAnswering(null);
    }
  }

  if (loading) return <TabLoading />;

  const open = probes.filter((p) => p.status === "open");
  const answered = probes.filter((p) => p.status === "answered");

  if (probes.length === 0) {
    return (
      <EmptyState
        icon={<BrainCircuit className="h-8 w-8" />}
        heading="No open questions"
        body="When Audit Bee spots an ambiguity in a document, it will surface a specific question here for you to answer."
      />
    );
  }

  return (
    <div className="space-y-5">
      {open.length > 0 && (
        <section>
          <h2 className="text-xs font-medium text-[#5B6270] uppercase tracking-wide mb-3">
            Needs your input ({open.length})
          </h2>
          <div className="space-y-3">
            {open.map((probe) => (
              <div key={probe.id} className="bg-white rounded-lg border border-blue-200 shadow-card p-4">
                <div className="flex gap-2.5">
                  <BrainCircuit className="h-4 w-4 text-blue-500 mt-0.5 shrink-0" />
                  <p className="text-sm text-[#16181D] leading-relaxed flex-1">{probe.question}</p>
                </div>
                <div className="mt-3 flex gap-2">
                  <input
                    type="text"
                    value={answers[probe.id] ?? ""}
                    onChange={(e) =>
                      setAnswers((prev) => ({ ...prev, [probe.id]: e.target.value }))
                    }
                    onKeyDown={(e) => e.key === "Enter" && handleAnswer(probe)}
                    placeholder="Type your answer…"
                    className="flex-1 rounded-md border border-[#E6E8EC] px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#3B6CF6]"
                  />
                  <button
                    onClick={() => handleAnswer(probe)}
                    disabled={answering === probe.id || !answers[probe.id]?.trim()}
                    className="flex items-center gap-1.5 rounded-md bg-[#1F2A44] text-white px-3 py-1.5 text-sm font-medium disabled:opacity-50 hover:bg-[#283552] transition-colors"
                  >
                    {answering === probe.id ? <Spinner className="h-3.5 w-3.5" /> : <Send className="h-3.5 w-3.5" />}
                    Answer
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {answered.length > 0 && (
        <section>
          <h2 className="text-xs font-medium text-[#5B6270] uppercase tracking-wide mb-3">
            Answered ({answered.length})
          </h2>
          <div className="space-y-2">
            {answered.map((probe) => (
              <div key={probe.id} className="bg-[#F7F8FA] rounded-lg border border-[#E6E8EC] p-4">
                <p className="text-sm text-[#5B6270]">{probe.question}</p>
                <p className="text-sm text-[#16181D] mt-1.5 font-medium">
                  → {probe.answer}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

// ── Reminders tab ─────────────────────────────────────────────────────────────

function RemindersTab({ clientId }: { clientId: string }) {
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [loading, setLoading] = useState(true);
  const [drafting, setDrafting] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Record<string, { subject: string; body: string }>>({});
  const [sending, setSending] = useState<string | null>(null);

  useEffect(() => {
    api.reminders(clientId).then(setReminders).finally(() => setLoading(false));
  }, [clientId]);

  async function handleDraft() {
    setDraftError(null);
    setDrafting(true);
    try {
      const reminder = await api.draftReminder(clientId);
      setReminders((prev) => [reminder, ...prev]);
      setEditing((prev) => ({
        ...prev,
        [reminder.id]: { subject: reminder.draft_subject, body: reminder.draft_body },
      }));
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "";
      if (msg.includes("No pending")) {
        setDraftError("No pending documents — nothing to remind the client about.");
      } else {
        setDraftError("Couldn't draft reminder right now. Try again in a moment.");
      }
    } finally {
      setDrafting(false);
    }
  }

  async function handleSend(reminder: Reminder) {
    setSending(reminder.id);
    const edit = editing[reminder.id];
    try {
      const updated = await api.sendReminder(
        clientId,
        reminder.id,
        edit?.subject ?? reminder.draft_subject,
        edit?.body ?? reminder.draft_body
      );
      setReminders((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
    } finally {
      setSending(null);
    }
  }

  if (loading) return <TabLoading />;

  const drafts = reminders.filter((r) => r.status === "draft");
  const sent = reminders.filter((r) => r.status === "sent");

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <p className="text-sm text-[#5B6270]">
          Draft a reminder email for outstanding documents.
        </p>
        <button
          onClick={handleDraft}
          disabled={drafting}
          className="flex items-center gap-2 rounded-md bg-[#1F2A44] text-white px-4 py-2 text-sm font-medium hover:bg-[#283552] disabled:opacity-60 transition-colors"
        >
          {drafting ? <Spinner className="h-4 w-4" /> : <Mail className="h-4 w-4" />}
          {drafting ? "Drafting with AI…" : "Draft reminder"}
        </button>
      </div>

      {draftError && (
        <div className="flex items-center gap-2 text-sm text-rose-600 bg-rose-50 border border-rose-200 rounded-lg px-4 py-3">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {draftError}
        </div>
      )}

      {drafts.length === 0 && sent.length === 0 && !drafting && !draftError && (
        <EmptyState
          icon={<Mail className="h-8 w-8" />}
          heading="No reminders yet"
          body={'Click "Draft reminder" — Audit Bee will write a warm, specific email based on what\'s still pending.'}
        />
      )}

      {drafts.map((reminder) => {
        const edit = editing[reminder.id];
        return (
          <div key={reminder.id} className="bg-white rounded-lg border border-amber-200 shadow-card overflow-hidden">
            <div className="px-4 py-2.5 bg-amber-50 border-b border-amber-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <StatusBadge status="draft" />
                <span className="text-xs text-[#5B6270]">AI-drafted — review before sending</span>
              </div>
            </div>
            <div className="p-4 space-y-3">
              <div>
                <label className="block text-xs font-medium text-[#5B6270] mb-1">Subject</label>
                <input
                  type="text"
                  value={edit?.subject ?? reminder.draft_subject}
                  onChange={(e) =>
                    setEditing((prev) => ({
                      ...prev,
                      [reminder.id]: { ...prev[reminder.id], subject: e.target.value },
                    }))
                  }
                  className="w-full rounded-md border border-[#E6E8EC] px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#3B6CF6]"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-[#5B6270] mb-1">Body</label>
                <textarea
                  rows={6}
                  value={edit?.body ?? reminder.draft_body}
                  onChange={(e) =>
                    setEditing((prev) => ({
                      ...prev,
                      [reminder.id]: { ...prev[reminder.id], body: e.target.value },
                    }))
                  }
                  className="w-full rounded-md border border-[#E6E8EC] px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#3B6CF6] resize-none"
                />
              </div>
              <div className="flex justify-end">
                <button
                  onClick={() => handleSend(reminder)}
                  disabled={sending === reminder.id}
                  className="flex items-center gap-2 rounded-md bg-[#3B6CF6] text-white px-4 py-2 text-sm font-medium hover:bg-[#2d5ed4] disabled:opacity-60 transition-colors"
                >
                  {sending === reminder.id ? <Spinner className="h-4 w-4" /> : <Send className="h-4 w-4" />}
                  {sending === reminder.id ? "Sending…" : "Send"}
                </button>
              </div>
            </div>
          </div>
        );
      })}

      {sent.length > 0 && (
        <section>
          <h2 className="text-xs font-medium text-[#5B6270] uppercase tracking-wide mb-3">Sent</h2>
          <div className="space-y-2">
            {sent.map((reminder) => (
              <div key={reminder.id} className="bg-[#F7F8FA] rounded-lg border border-[#E6E8EC] p-4">
                <div className="flex items-center justify-between mb-2">
                  <StatusBadge status="sent" />
                  <span className="text-[10px] text-[#5B6270]">
                    {reminder.sent_at
                      ? new Date(reminder.sent_at).toLocaleDateString("en-US", {
                          month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                        })
                      : ""}
                  </span>
                </div>
                <p className="text-sm font-medium text-[#16181D]">{reminder.draft_subject}</p>
                <p className="text-xs text-[#5B6270] mt-1 whitespace-pre-wrap leading-relaxed">
                  {reminder.draft_body}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

// ── Shared ─────────────────────────────────────────────────────────────────────

function TabLoading() {
  return (
    <div className="flex justify-center py-12">
      <Spinner className="h-5 w-5 text-[#5B6270]" />
    </div>
  );
}
