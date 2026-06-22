# Design Document: Audit Bee

## AI Document Intake & Triage for a Multi-CPA Tax Firm — Interview Demo Build

---

## 0. Intent of This Build (Read First)

This is a **working, scoped demo application** built for a second-round interview with the firm's CEO. It is not the production deliverable. Its job is to prove three things:

1. The pain points the CEO described were heard and understood.
2. Those pain points were turned into a real, playable system, not a slide deck or a clickable prototype.
3. The builder can ship something polished and secure fast.

**The firm's reality (from the conversations):** many CPAs, each managing many clients, mostly tax work, drowning in manuals and manual process. The tools they use don't talk to each other, so document intake, sorting, and client follow-up are all done by hand.

**What is real in this build:** the AI document pipeline, the data model, authentication, authorization, role-based access, secure document storage, the audit log, and the full UI. These work end to end.

**What is deliberately simulated:** third-party integrations (Gmail, DocuSign, Calendly, QuickBooks) appear as "Connected" surfaces and a "simulate inbound email" action, but no real OAuth handshakes are built. Scheduled "business-hours send" is simulated. This is stated openly in the demo so the simulation reads as scoping discipline, not as smoke.

**Two open decisions resolved by default (adjust if the firm signalled otherwise):**
- **Spotlighted pains:** (a) hand-sorting and renaming incoming documents, (b) manually chasing clients for missing paperwork, (c) re-keying data between disconnected tools.
- **Delivery:** deployed to a live URL the CEO can click through, with local Docker for development and screen-share-driven walkthrough as a fallback.

---

## 1. Problem Statement

A mid-size CPA firm runs tax and advisory work for hundreds of clients across a handful of CPAs. For every client, documents arrive in a trickle over weeks: W-2s, 1099s, mortgage interest statements, K-1s, prior-year returns, bank statements. They arrive through a portal, over email, and as physical paper that gets scanned.

Today, a person opens each file, figures out what it is, renames it to the firm's convention, drops it in the right client folder, mentally tracks what's still missing, and emails the client to chase the gaps. Multiply that across every CPA and every client and the firm spends an enormous fraction of its time on document choreography rather than accounting. The firm's software doesn't help: the portal, the email, and the tax software are separate islands, and moving information between them is manual.

**The gap:** there is no system that ingests documents from any channel, understands what each one is, tracks what each client still owes, and drafts the follow-up — while keeping every client's sensitive financial data strictly walled off from everyone who shouldn't see it.

---

## 2. Solution Overview

Audit Bee is an AI intake and triage layer that sits between the firm and its clients. A client uploads a document; Audit Bee reads it, classifies it, renames it to convention, extracts the key fields into a running context record, checks it against that client's required-document checklist, and surfaces what's still missing along with a drafted reminder the CPA can send in one click.

**The core insight:** the firm's bottleneck is not tax computation — that's a solved, regulated problem owned by their tax software. The bottleneck is the manual document workflow wrapped around it. Audit Bee automates that wrapper and becomes the connective tissue the firm's disconnected tools never provided.

**The security insight:** a system that touches every client's tax documents lives or dies on access control. Audit Bee is built so that authorization is enforced on every single data access, server-side, against the authenticated user — a client can never see another client's documents, and a CPA can never see a client they aren't assigned to. This is the feature a CPA firm cares about most, and it is built for real.

---

## 3. User Journeys

### 3.1 Client (external)
1. Receives an email invitation from their CPA with a secure link.
2. Opens the link, sets a password, lands in a clean portal scoped to only their case.
3. Uploads a tax document.
4. Watches it get accepted and processed ("Received → Reading → Classified").
5. Sees their checklist: what's been received, what's still outstanding.
6. Receives reminders for missing documents.

### 3.2 CPA (internal)
1. Logs in to a dashboard of only their assigned clients.
2. Sees a notification that a client uploaded something.
3. Opens the client and reviews Audit Bee's work: the document, its detected type, its new name, the extracted fields.
4. Checks the Pending tab: what this client still owes.
5. Reviews an AI-drafted reminder email, edits if needed, and sends it.
6. Answers a context-probe when Audit Bee flags that something is ambiguous.

### 3.3 Admin / Partner (internal)
1. Logs in to a firm-wide view across all CPAs and clients.
2. Manages users: invites CPAs, assigns clients to CPAs, invites clients.
3. Reviews the audit log of who accessed what.

**Wow moments, flagged for the demo:** the live classification + auto-rename (3.2 step 3), the one-click AI-drafted reminder (3.2 step 5), the context-probe (3.2 step 6), and the visible access wall (a client literally cannot load another client's document).

---

## 4. Architecture

### 4.1 High-Level Flow

```
                          ┌─────────────────────────────────────────┐
                          │              Audit Bee API               │
                          │                (FastAPI)                 │
  Upload (portal) ──────► │                                          │
  Simulated email ──────► │  Auth + AuthZ ─► Secure Store ─► Queue   │
  Simulated scan  ──────► │                                    │     │
                          │                                    ▼     │
                          │   ┌──────────── Processing ──────────┐   │
                          │   │ Claude: classify ─► extract ─►   │   │
                          │   │ rename ─► update context ─►      │   │
                          │   │ check checklist ─► flag gaps ─►  │   │
                          │   │ (optional) raise context-probe   │   │
                          │   └──────────────────────────────────┘   │
                          │                    │                     │
                          │       Postgres + Audit Log + Files       │
                          └────────────────────┬─────────────────────┘
                                               │
                                   React + Tailwind + shadcn/ui
                              (Client portal · CPA dash · Admin · Audit)
```

### 4.2 Component Breakdown

| Component | Responsibility | Technology |
|-----------|----------------|------------|
| API server | Routing, auth, authorization, orchestration | FastAPI |
| Auth service | Login, invite tokens, password hashing, sessions | python-jose (JWT) + argon2 |
| Authorization layer | Object-level access checks on every resource | FastAPI dependencies + scoped queries |
| Document store | Encrypted-at-rest files, served only via authorized routes | Local disk (demo) / S3-compatible (prod swap) |
| Processing pipeline | Classify, extract, rename, gap-check, probe | Claude API + FastAPI BackgroundTasks |
| Checklist engine | Per-client required-doc tracking and gap detection | Postgres + service logic |
| Notification service | AI-drafted reminders, send/schedule (simulated) | Claude API + service logic |
| Audit logger | Append-only record of access and mutations | Postgres |
| Integrations (simulated) | "Connected" surfaces + simulate-inbound-email | Service stubs |
| Synthetic data generator | Realistic fake clients and tax PDFs | Claude API + WeasyPrint |
| Frontend | Portal, CPA dashboard, admin, audit views | React + Vite + TS + Tailwind + shadcn/ui |

### 4.3 Data Model

```
Firm (1) ──< User (admin | cpa | client)
Firm (1) ──< Client ──< Document
                   │ └──< RequiredDocument (checklist)
                   │ └──< ContextEntry
                   │ └──< ContextProbe
                   │ └──< Reminder
User (cpa) (1) ──< Client (assignment)
User (1) ──< AuditLog
Firm (1) ──< Integration (simulated)
```

**User:** `id, firm_id, email, password_hash, role, name, client_id (nullable), is_active, created_at`
**Client:** `id, firm_id, name, type (individual|business), assigned_cpa_id, tax_year, email, created_at`
**Document:** `id, client_id, uploaded_by, original_filename, normalized_filename, storage_key, doc_type, tax_year, status (processing|classified|needs_review|error), extracted_summary, extracted_fields (jsonb), source_channel (portal|email_sim|scan_sim), uploaded_at, processed_at`
**RequiredDocument:** `id, client_id, doc_type, label, required (bool), status (pending|received), satisfied_by_document_id (nullable)`
**ContextEntry:** `id, client_id, content, source (document|cpa_note|probe_answer), created_by, created_at`
**ContextProbe:** `id, client_id, question, status (open|answered), answer, created_at, answered_by`
**Reminder:** `id, client_id, channel (email_sim), draft_subject, draft_body, status (draft|sent|scheduled), scheduled_for, created_by, sent_at`
**AuditLog:** `id, user_id, action, resource_type, resource_id, ip, detail (jsonb), created_at`
**Integration:** `id, firm_id, name, status (connected|disconnected), connected_at`

---

## 5. Security & IAM Architecture

This section is first-class because the firm handles sensitive financial data and a leak is the worst possible demo outcome. The principle is simple: **never trust the client for an access decision, and check authorization on every resource access, server-side.**

### 5.1 Authentication
- **Staff (admin, cpa):** email + password. Passwords hashed with **argon2id** (never stored or logged in plaintext). Admin seeds the first admin; admins create CPAs.
- **Clients:** onboarded via a **signed, single-use, time-limited invite token** emailed by their CPA. The token is a JWT with `purpose=invite`, the `client_id`, and a short expiry; redeeming it lets the client set a password and creates their `client` user. Tokens are invalidated after use.
- **Sessions:** short-lived access JWT + refresh token. Access tokens carry `user_id`, `role`, `firm_id`, and (for clients) `client_id`. Tokens are signed with a secret from the environment, never embedded in code or the frontend bundle.

### 5.2 Authorization (the no-leak core)
- **Role gate (coarse):** route-level dependency asserting the role is permitted (e.g., only `admin` can manage users).
- **Object-level gate (fine, mandatory):** every endpoint that reads or mutates client data resolves the resource and asserts the authenticated user is allowed to touch *that specific resource*:
  - `client` role → only resources where `resource.client_id == user.client_id`.
  - `cpa` role → only clients where `client.assigned_cpa_id == user.id`, and documents/checklist/context belonging to those clients.
  - `admin` role → all resources within `user.firm_id`.
- **Scoped queries, not post-filtering:** list endpoints filter in the query (`WHERE client_id IN (assigned clients)`), so unauthorized rows are never loaded, let alone returned. There is no code path that fetches by raw ID and trusts it.
- **No IDOR:** requesting `/documents/{id}` for a document you don't own returns **404** (not 403 — don't confirm existence). This closes insecure direct object reference, the most common way these systems leak.

### 5.3 Document storage
- Files are stored **outside any static/public directory**, keyed by an opaque `storage_key` (UUID), never by filename.
- Files are served **only** through an authenticated, authorized FastAPI route that runs the same object-level check and streams the bytes. There are no public file URLs.
- For the demo, files live on local disk with the path derived from the opaque key. Production swap: S3 with private ACLs and short-lived presigned URLs.

### 5.4 Encryption
- **In transit:** HTTPS/TLS everywhere (handled at the deploy/proxy layer).
- **At rest:** disk/volume encryption on the host; sensitive extracted fields (e.g., the last four of an SSN) stored masked, never the full value.

### 5.5 Audit logging
Every authentication event, document access, document download, reminder send, and user-management action writes an append-only `AuditLog` row with actor, action, resource, IP, and timestamp. This is both a real security control and a demo asset: showing a CEO a clean "who-touched-what" trail lands hard with a compliance-minded firm.

### 5.6 Supporting controls
- Upload validation: allow-list of MIME types (PDF, common image types), max file size, magic-byte sniffing (don't trust the extension).
- Secrets via environment only (`.env` git-ignored; `ANTHROPIC_API_KEY`, `JWT_SECRET`, DB URL).
- Basic rate limiting on auth endpoints to blunt brute force.
- Generic auth errors ("invalid email or password") that don't reveal which field was wrong.
- CORS locked to the known frontend origin.

### 5.7 Demo-grade vs production (stated honestly)
Real in this build: argon2 hashing, JWT sessions, object-level authz on every endpoint, no-IDOR 404s, scoped queries, private file serving, audit log, upload validation. Deferred to production: full secrets manager (KMS/Vault), per-field envelope encryption, SSO/SAML, WAF, pen-test hardening, and key rotation. The core that prevents data leaks is built now.

---

## 6. Key Design Decisions

### 6.1 No orchestration engine for the demo
**Decision:** Run document processing as a FastAPI `BackgroundTask` with status surfaced to the UI by polling (or a WebSocket if time allows). No Celery, no Temporal, no n8n.
**Rationale:** The volume is a handful of documents. A background task plus a live "Processing → Classified" status gives the real-system feel with zero extra infrastructure to stand up or debug under deadline. The heavier orchestration belongs in the production roadmap, not the interview.

### 6.2 Claude for classify + extract, with strict structured output
**Decision:** One Claude call per document returns classification, extracted fields, and a one-line summary as strict JSON.
**Rationale:** Determinism and parseability. Prompt the model to return JSON only, parse defensively, and route any parse failure to `needs_review` rather than crashing.

**Prompt template:**
```
You are a tax document classifier for a CPA firm. Given the text of one
document, identify it and extract key fields. Respond with ONLY valid JSON,
no prose, no markdown fences.

{
  "doc_type": "one of: W-2, 1099-NEC, 1099-INT, 1099-DIV, 1098, K-1,
               prior_year_return, bank_statement, engagement_letter, other",
  "tax_year": "YYYY or null",
  "summary": "one sentence, plain language",
  "fields": { "issuer": "...", "recipient": "...", "key_amounts": {...} },
  "confidence": 0.0
}

If the document is unclear, set doc_type to "other" and confidence below 0.5.

Document text:
{document_text}
```

### 6.3 Auto-rename convention with preserved original
**Decision:** Normalized name = `{ClientLastName}_{DocType}_{TaxYear}.pdf`. The original filename is always retained on the record.
**Rationale:** Provenance is sacred to accountants. The clean name is a display/convenience layer; the original is never destroyed, and the audit log records both.

### 6.4 Checklist-driven gap detection
**Decision:** Each client is seeded with a required-document checklist based on their type (individual vs business). When a document is classified, the matching checklist item flips to `received`; everything still `pending` is the gap.
**Rationale:** "What's missing" needs a source of truth. A per-client checklist makes the Pending tab meaningful and drives reminders. It also makes the demo legible: the CEO sees exactly why a client is incomplete.

**Example checklists:**
- Individual: W-2, 1099-INT, 1099-DIV, 1098, prior_year_return
- Business: profit_and_loss, balance_sheet, 1099-NEC, bank_statement, prior_year_return

### 6.5 Context-probe (signature wow feature)
**Decision:** After processing, optionally run a second Claude call that judges whether the client's context is sufficient to proceed and, if not, generates one specific question for the CPA.
**Rationale:** This is what separates "smart assistant" from "OCR." A vague probe is useless; a specific one ("This client's W-2 lists two employers — is the second a current job or prior-year?") is the moment the CEO leans in. Probes are tied to a purpose, surfaced to the assigned CPA only.

**Prompt template:**
```
You are assisting a CPA. Given a client's current document context, decide
whether anything is ambiguous enough to need the CPA's input before the
return can proceed. Respond ONLY as JSON:

{ "needs_input": true|false, "question": "one specific question or null" }

Only flag genuine ambiguities. Do not nitpick. Context:
{client_context}
```

### 6.6 AI-drafted reminders, human-in-the-loop
**Decision:** Audit Bee drafts the chase email from the client's pending list; the CPA reviews, edits, and sends. Nothing is auto-sent.
**Rationale:** Tone and accuracy matter to client relationships, and a human gate makes the AI's occasional miss low-stakes. The "send" is simulated (logged + shown as sent) but the draft quality is real.

**Prompt template:**
```
Draft a short, warm, professional email from a CPA to a tax client
reminding them of outstanding documents. Plain text, no placeholders left
unfilled. Client: {client_name}. Still needed: {pending_items}.
Return JSON: { "subject": "...", "body": "..." }
```

### 6.7 Object-level authorization as a shared dependency
**Decision:** A reusable FastAPI dependency resolves the target resource and enforces the 5.2 rules; every data endpoint depends on it.
**Rationale:** Centralizing the check means it can't be forgotten per-endpoint. This is the single most important pattern in the codebase and is called out to Claude Code as a hard requirement.

```python
def authorize_client_access(client_id, user) -> Client:
    client = get_client_or_none(client_id)
    if client is None or client.firm_id != user.firm_id:
        raise HTTPException(404)
    if user.role == "client" and user.client_id != client.id:
        raise HTTPException(404)
    if user.role == "cpa" and client.assigned_cpa_id != user.id:
        raise HTTPException(404)
    return client  # admin within firm passes
```

### 6.8 Simulated integrations, honestly framed
**Decision:** Gmail / DocuSign / Calendly / QuickBooks render as a Connections page with "Connected" status; a "Simulate inbound email" action drops a document into a client's intake exactly as a portal upload would.
**Rationale:** It tells the disconnected-tools story and demonstrates the channel-agnostic pipeline (all channels converge on the same processing) without building real OAuth under deadline. The simulation is disclosed in the demo.

### 6.9 Graceful AI failure
**Decision:** Wrap every Claude call in try/except with a timeout. On failure, mark the document `needs_review` with a friendly status and let the CPA reclassify manually; never surface a traceback.
**Rationale:** A demo that degrades cleanly survives a flaky moment; a demo that throws a 500 in front of the CEO does not.

### 6.10 Realistic synthetic data, generated not faked-by-hand
**Decision:** Generate the demo dataset programmatically: realistic clients, internally consistent documents, rendered as genuine-looking PDFs (Section 8).
**Rationale:** The whole demo's credibility rests on the documents looking real. Hand-made stubs read as toys.

---

## 7. Technical Stack

| Layer | Technology | Reason |
|-------|------------|--------|
| API | FastAPI (Python) | Known well; async; fast to build |
| AI | Claude API — `claude-sonnet-4-6` | Fast/cheap for the pipeline; swap to `claude-opus-4-8` for max extraction fidelity (volume is tiny) |
| DB | PostgreSQL | Production-like; jsonb for extracted fields |
| ORM / migrations | SQLAlchemy + Alembic | Standard, clean schema management |
| Auth | python-jose (JWT) + argon2-cffi | Strong hashing, stateless sessions |
| Files | Local disk (demo) → S3-compatible (prod) | Private, authorized serving |
| PDF generation | WeasyPrint (HTML→PDF) | Realistic, templatable tax documents |
| PDF parsing | pdfplumber | Reliable text + table extraction |
| Frontend | React + Vite + TypeScript | Known; fast dev loop |
| UI kit | Tailwind + shadcn/ui | Polished, consistent, fast to assemble |
| Packaging | Docker + docker-compose | One-command local bring-up |
| Deploy | Render/Railway (API + Postgres) + Vercel (frontend) | Live URL for the CEO |

---

## 8. Synthetic Tax Document Generation

The demo must open onto a populated, believable firm. Approach:

1. **Generate client profiles** with Claude: ~5 clients across 2–3 CPAs, a mix of individuals and one or two businesses, each with a coherent backstory (job, employer, bank, mortgage status).
2. **Generate consistent field data** per document so a client's W-2 employer matches their profile, amounts are plausible, and figures reconcile across documents.
3. **Render to PDF** from HTML templates via WeasyPrint, one template per doc type (W-2, 1099-NEC, 1099-INT, 1098, prior-year 1040 summary, bank statement, engagement letter). Templates mimic the real forms' layout closely enough to read as authentic on screen.
4. **Use only fake identifiers:** placeholder SSNs/EINs in valid *format* but obviously non-real (e.g., `000-00-XXXX`), fictional names and addresses.
5. **Seed the database** so each client has *some* documents already received and *some* still pending — this is what makes the Pending tab and reminders demonstrable on open.

This generator is itself a script (`scripts/seed_demo.py`) so the demo dataset can be regenerated cleanly before the interview.

---

## 9. Build Plan (Phase by Phase)

Solo, roughly 2–3 focused days. Each phase ends in a committable, working state. Auth/security is front-loaded because it's foundational and emphasized.

| Phase | Deliverable | "Done" looks like | Est. |
|-------|-------------|-------------------|------|
| 0 | Scaffold: monorepo, FastAPI skeleton, Vite/React skeleton, Postgres via docker-compose, env config, linting | `docker-compose up` serves an API health check and a blank styled frontend | 1.5h |
| 1 | Data model + Alembic migrations + seed framework | All tables migrate; a script can insert a firm + admin | 1.5h |
| 2 | Auth + IAM: argon2, JWT, invite tokens, login, the `authorize_*` dependencies | Staff can log in; clients redeem invites; object-level checks enforced and unit-tested | 4h |
| 3 | Document upload + secure private storage + audit logging | Authorized upload stores a file by opaque key; download route enforces access; every access logged | 2.5h |
| 4 | Processing pipeline: Claude classify/extract, auto-rename, live status | Upload triggers background processing; UI shows Processing→Classified; fields populated | 3h |
| 5 | Checklist engine + Context tab + Pending tab | Classified docs satisfy checklist items; gaps surface; context trail renders | 2.5h |
| 6 | Wow features: AI-drafted reminders + context-probe | CPA reviews/sends a drafted reminder; probes appear and can be answered | 2.5h |
| 7 | Simulated integrations + simulate-inbound-email + Connections page | "Connected" surfaces; simulated email drops a doc into intake | 1.5h |
| 8 | Synthetic data generator + seed a realistic demo dataset | Five clients, real-looking PDFs, mixed received/pending state | 3h |
| 9 | Frontend polish: corporate-SaaS design system, all states (empty/loading/error), role-specific shells | Looks like a shipped product; no rough edges in the demo path | 4h |
| 10 | Deploy + demo dry-run + contingency | Live URL works; full demo script runs clean twice | 2h |

### 9.1 Frontend Design Direction (clean corporate SaaS)
A restrained, trustworthy product look — calm, precise, finance-appropriate. Not the generic AI-default cream-serif look.

- **Palette:** white and near-white surfaces (`#FFFFFF`, `#F7F8FA`), a deep slate-indigo primary for brand and primary actions (`#1F2A44`), a single confident action accent (`#3B6CF6`), hairline borders (`#E6E8EC`), ink text (`#16181D` / muted `#5B6270`). Status colors: received (green), pending (amber), processing (blue), needs-review (rose).
- **Type:** Inter for UI text with a clear scale and intentional weights; a monospace (IBM Plex Mono) for amounts, IDs, and tax figures — a domain-true touch that makes financial data read as precise.
- **Layout:** left nav rail, generous whitespace, content in cards with quiet shadows and clear hierarchy. Role-specific shells (client portal is minimal and reassuring; CPA dash is dense and efficient; admin is structural).
- **Signature element:** the document-processing reveal — a document card that animates through Received → Reading → Classified and then surfaces the extracted fields cleanly. This is the memorable moment; keep everything around it disciplined.
- **Quality floor:** responsive to mobile, visible keyboard focus, reduced-motion respected, every empty state written as a direction ("No documents yet — upload one to get started"), every error stated plainly with a fix.

---

## 10. Demo Script (~4 Minutes)

**0:00–0:30 — The Hook**
> "Last time we talked, you told me documents come in three ways — your portal, email, and scanned paper — and that sorting them, renaming them, and chasing clients for what's missing is all done by hand, because none of your tools talk to each other. So I built the thing that does it. This is live."

**0:30–1:45 — The Core Loop (as a CPA)**
- Log in as a CPA → dashboard of assigned clients, one flagged "new upload."
- Open the client. Upload a W-2 (or show one just uploaded).
- The card animates: Received → Reading → **Classified as W-2**, auto-renamed `Patel_W-2_2024.pdf`, employer and wages extracted into context.
> "It read the document, named it to your convention, and filed the data — the thing that used to take a person a minute per file, across hundreds of files."
- Open the Pending tab: "still missing: 1099-INT, prior-year return."
- Click "Draft reminder" → a warm, specific email appears, pre-filled. Edit a word, send.
> "It wrote the chase email for you."

**1:45–2:30 — The Wow (context-probe + the wall)**
- A context-probe is waiting: a sharp, specific question about an ambiguity. Answer it; it folds into the client's context.
> "It doesn't just scan — it notices when something's unclear and asks."
- Open a second browser as a *client*. Show that the client sees only their own documents, and that trying to reach another client's file returns nothing.
> "This is the part that matters most for you: a client can never see another client's data, and a CPA only sees their own clients. That's enforced on every request, not just hidden in the UI."

**2:30–3:15 — The Integration Story**
- Open Connections: Gmail, DocuSign, Calendly, QuickBooks shown "Connected."
- Click "Simulate inbound email" → a document lands in a client's intake and runs through the exact same pipeline.
> "Every channel feeds one brain. Your tools finally talk to each other."
- Open the Audit log: a clean who-touched-what trail.

**3:15–4:00 — The Close**
> "I built this in a few days after our conversation, scoped to exactly what you described. It's a demo — the integrations here are simulated and there's a real production roadmap behind it — but the AI pipeline, the security, and the access control are real and running. This is what it looks like when your document workflow runs itself."

---

## 11. Contingency Plan

| Failure | Response |
|---------|----------|
| Claude call fails mid-demo | Document lands in `needs_review`; reclassify manually in one click; narrate it as the built-in graceful-failure path |
| Deployed URL down | Fall back to local `docker-compose up` and screen-share |
| Upload misbehaves | Pre-seeded documents already demonstrate the full pipeline; pivot to those |
| Network flaky | Run entirely local; the app has no hard cloud dependency except the Claude API |
| Time runs short in build | Phases 7 and parts of 9 are the first to trim; the core loop (2–6) is the non-negotiable spine |

---

## 12. Design Sign-off

All design decisions documented and owned. Security and IAM specified to the
endpoint level with no-leak authorization as a hard, central requirement.
Build sequenced into committable phases with auth front-loaded. Synthetic data
strategy defined for realism. Build prompts live in the companion file
`audit_bee_build_prompts.md`; this document remains the single source of truth.

**Status:** ready to build.

---

*End of Design Document*
