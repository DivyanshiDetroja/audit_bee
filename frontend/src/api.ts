const BASE: string = import.meta.env.VITE_API_BASE_URL ?? "/api";

function getToken(): string | null {
  return localStorage.getItem("access_token");
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem("access_token", access);
  localStorage.setItem("refresh_token", refresh);
}

function clearTokens() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.body && !(options.body instanceof FormData)
      ? { "Content-Type": "application/json" }
      : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers as Record<string, string>),
  };

  const res = await fetch(`${BASE}${path}`, { ...options, headers });

  if (res.status === 401) {
    clearTokens();
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw Object.assign(new Error(body.detail ?? "Request failed"), {
      status: res.status,
      body,
    });
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function login(email: string, password: string): Promise<void> {
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw Object.assign(new Error(body.detail ?? "Login failed"), {
      status: res.status,
    });
  }
  const data = await res.json();
  setTokens(data.access_token, data.refresh_token);
}

export function logout() {
  clearTokens();
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  firm_id: string;
  email: string;
  name: string;
  role: "admin" | "cpa" | "client";
  client_id: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Client {
  id: string;
  firm_id: string;
  name: string;
  type: "individual" | "business";
  assigned_cpa_id: string | null;
  created_at: string;
  pending_count: number;
}

export interface Document {
  id: string;
  client_id: string;
  original_filename: string;
  normalized_filename: string | null;
  doc_type: string | null;
  tax_year: number | null;
  mime_type: string | null;
  status: "processing" | "classified" | "needs_review" | "error";
  extracted_summary: string | null;
  extracted_fields: Record<string, unknown> | null;
  source_channel: "portal" | "email_sim" | "scan_sim";
  uploaded_at: string;
  processed_at: string | null;
}

export interface RequiredDocument {
  id: string;
  client_id: string;
  doc_type: string;
  label: string;
  required: boolean;
  status: "pending" | "received";
  satisfied_by_document_id: string | null;
}

export interface ContextEntry {
  id: string;
  client_id: string;
  content: string;
  source: "document" | "cpa_note" | "probe_answer";
  created_at: string;
}

export interface ContextProbe {
  id: string;
  client_id: string;
  question: string;
  status: "open" | "answered";
  answer: string | null;
  created_at: string;
}

export interface Reminder {
  id: string;
  client_id: string;
  draft_subject: string;
  draft_body: string;
  status: "draft" | "sent";
  channel: string;
  sent_at: string | null;
  created_at: string;
}

export interface Integration {
  id: string;
  firm_id: string;
  name: string;
  status: "connected" | "disconnected";
  connected_at: string | null;
}

export interface AuditLog {
  id: string;
  user_id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  ip: string | null;
  detail: Record<string, unknown>;
  created_at: string;
}

// ── API calls ─────────────────────────────────────────────────────────────────

export const api = {
  // Users / Auth
  me(): Promise<User> {
    return request("/auth/me");
  },
  users(): Promise<User[]> {
    return request("/auth/users");
  },

  // Clients
  clients(): Promise<Client[]> {
    return request("/auth/clients-list");
  },
  client(id: string): Promise<Client> {
    return request(`/auth/clients-list/${id}`);
  },
  assignCPA(clientId: string, assignedCpaId: string | null): Promise<Client> {
    return request(`/auth/clients-list/${clientId}/assign`, {
      method: "PATCH",
      body: JSON.stringify({ assigned_cpa_id: assignedCpaId }),
    });
  },
  inviteClient(clientId: string, email: string): Promise<{ invite_token: string }> {
    return request(`/auth/clients-list/${clientId}/invite`, {
      method: "POST",
      body: JSON.stringify({ email }),
    });
  },
  redeemInvite(token: string, name: string, password: string): Promise<{ access_token: string; refresh_token: string }> {
    return request("/auth/redeem", {
      method: "POST",
      body: JSON.stringify({ invite_token: token, name, password }),
    });
  },

  // Documents
  clientDocuments(clientId: string): Promise<Document[]> {
    return request(`/clients/${clientId}/documents`);
  },
  uploadDocument(clientId: string, file: File): Promise<Document> {
    const form = new FormData();
    form.append("file", file);
    return request(`/clients/${clientId}/documents`, {
      method: "POST",
      body: form,
    });
  },
  simulateEmail(clientId: string, file: File, fromAddress: string): Promise<Document> {
    const form = new FormData();
    form.append("file", file);
    form.append("from_address", fromAddress);
    return request(`/clients/${clientId}/simulate-email`, {
      method: "POST",
      body: form,
    });
  },

  // Checklist
  checklist(clientId: string): Promise<RequiredDocument[]> {
    return request(`/clients/${clientId}/checklist`);
  },
  pending(clientId: string): Promise<RequiredDocument[]> {
    return request(`/clients/${clientId}/pending`);
  },

  // Context
  context(clientId: string): Promise<ContextEntry[]> {
    return request(`/clients/${clientId}/context`);
  },

  // Probes
  probes(clientId: string, status?: string): Promise<ContextProbe[]> {
    const q = status ? `?status=${status}` : "";
    return request(`/clients/${clientId}/probes${q}`);
  },
  answerProbe(
    clientId: string,
    probeId: string,
    answer: string
  ): Promise<ContextProbe> {
    return request(`/clients/${clientId}/probes/${probeId}/answer`, {
      method: "POST",
      body: JSON.stringify({ answer }),
    });
  },

  // Reminders
  reminders(clientId: string): Promise<Reminder[]> {
    return request(`/clients/${clientId}/reminders`);
  },
  draftReminder(clientId: string): Promise<Reminder> {
    return request(`/clients/${clientId}/reminders/draft`, { method: "POST" });
  },
  sendReminder(
    clientId: string,
    reminderId: string,
    subject: string,
    body: string
  ): Promise<Reminder> {
    return request(`/clients/${clientId}/reminders/${reminderId}/send`, {
      method: "POST",
      body: JSON.stringify({ subject, body }),
    });
  },

  // Integrations
  integrations(): Promise<Integration[]> {
    return request("/integrations");
  },
  toggleIntegration(id: string): Promise<Integration> {
    return request(`/integrations/${id}/toggle`, { method: "POST" });
  },

  // Audit log (admin)
  auditLog(): Promise<AuditLog[]> {
    return request("/auth/audit-log");
  },
  // Users list (admin)
  usersList(): Promise<User[]> {
    return request("/auth/users");
  },
};
