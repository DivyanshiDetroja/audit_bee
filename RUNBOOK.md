# Audit Bee — Runbook

## 1. Local dev (docker-compose)

```bash
cp .env.example .env
# Fill in ANTHROPIC_API_KEY and JWT_SECRET in .env

docker compose up --build
# API:      http://localhost:8000
# Frontend: http://localhost:5173

# Seed demo data (first time or to reset):
docker compose exec backend python scripts/seed_demo.py
```

**Demo credentials (seeded):**

| Role  | Email                          | Password    |
|-------|--------------------------------|-------------|
| Admin | admin@acmecpa.com              | Admin1234!  |
| CPA   | david.nguyen@acmecpa.com       | Demo1234!   |
| CPA   | rachel.okonkwo@acmecpa.com     | Demo1234!   |
| CPA   | sandra.whitmore@acmecpa.com    | Demo1234!   |

Clients (Marcus J. Bellamy, Lena R. Castellanos, Theodore A. Winslow, Ironwood Creative Studios LLC, Pinnacle Logistics Solutions Inc.) are pre-seeded with 2 received docs + 3 pending checklist items each.

---

## 2. Deploy to Render (API + Postgres) + Vercel (frontend)

This is a two-step deploy. You need the Render URL before Vercel can be configured.

### Step A — Deploy the API to Render

1. Push the repo to GitHub.
2. Go to [render.com](https://render.com) → **New** → **Blueprint**.
3. Connect the repo. Render reads `render.yaml` and creates:
   - `audit-bee-api` (Docker web service on port 8000)
   - `audit-bee-db` (Postgres, free plan)
4. In the Render dashboard, set the two manual env vars on `audit-bee-api`:
   - `ANTHROPIC_API_KEY` → your key
   - `CORS_ORIGIN` → leave blank for now (fill in after Vercel deploy)
5. Deploy. On first boot, the `startCommand` runs `alembic upgrade head` then starts uvicorn.
6. Note your API URL: `https://audit-bee-api.onrender.com` (or similar).

### Step B — Deploy the frontend to Vercel

1. Go to [vercel.com](https://vercel.com) → **Add New Project** → import the GitHub repo.
2. Set **Root Directory** to `frontend`.
3. Add environment variable:
   - `VITE_API_BASE_URL` = `https://audit-bee-api.onrender.com` (your Render URL from Step A)
4. Vercel uses `vercel.json` (already in repo) for SPA routing rewrites.
5. Deploy. Note your Vercel URL: `https://audit-bee.vercel.app` (or similar).

### Step C — Wire CORS

1. Back in Render → `audit-bee-api` → Environment.
2. Set `CORS_ORIGIN` = your Vercel URL (e.g. `https://audit-bee.vercel.app`).
3. Redeploy (Render auto-redeploys on env var change).

### Step D — Warm up + seed demo data on Render

> **Cold start warning:** Render free services sleep after 15 min of inactivity. The first request after sleep takes ~30 seconds. Before any demo, open `https://audit-bee-api.onrender.com/health` in a browser and wait for `{"status":"ok"}` — this wakes the service so the demo starts instantly.

### Step E — Seed demo data on Render

```bash
# Using the Render shell (dashboard → audit-bee-api → Shell tab):
python scripts/seed_demo.py
```

---

## 3. Reseed demo data (reset for a fresh demo run)

The seed script is idempotent — it wipes all non-admin demo data and rebuilds.

**Local:**
```bash
docker compose exec backend python scripts/seed_demo.py
```

**Render:**
Use the Render web shell or SSH (see Step D above). Takes ~60s (Claude API call for profile generation + PDF rendering).

---

## 4. Local docker-compose fallback (offline demo)

If the live URL is unreachable during the demo:

```bash
docker compose up          # starts everything (no --build needed after first run)
# Navigate to http://localhost:5173
```

The app has no hard cloud dependency except the Anthropic Claude API. Ensure the machine has internet access for Claude calls (document processing and reminder drafting).

---

## 5. File storage note

Uploaded PDFs are stored at `/app/uploads/` on the backend container.

- **Local:** persisted via Docker volume (`postgres_data`). The uploads directory is bind-mounted from `./backend/uploads` so files survive container restarts.
- **Render free plan:** includes a 1 GB persistent disk mounted at `/app/uploads` (configured in `render.yaml`). Files survive redeploys.

Re-seeding generates fresh PDFs and re-saves them; it does not depend on previously uploaded files.

---

## 6. Demo script quick reference (§10)

1. Log in as CPA (`david.nguyen@acmecpa.com` / `Demo1234!`)
2. Client list → note the amber "X pending" badge — click a client (e.g. Marcus J. Bellamy)
3. **Documents tab** → upload a W-2 PDF → watch the card animate: Received → Reading → Classified → fields appear
4. **Pending tab** → show what's still missing
5. **Reminders tab** → "Draft reminder" → AI writes the email → edit one word → Send
6. **Probes tab** → answer the open question → it folds into Context
7. Open a second browser as a client (use the invite flow from the client header, or log in if already redeemed)
8. Show client sees only their own docs — entering another client's URL returns nothing
9. **Connections page** → show Gmail/DocuSign/etc Connected → drop a PDF in "Simulate inbound email" → auto-redirects to client with new document processing
10. Admin login (`admin@acmecpa.com` / `Admin1234!`) → **Audit Log** → clean who-touched-what trail
