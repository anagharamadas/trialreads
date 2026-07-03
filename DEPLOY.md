# Deployment — TrialReads (Milestone 5)

Backend → **Render**, Frontend → **Vercel**, Database/Auth → **Supabase** (already live).

Order matters: deploy the **backend first** (you need its public URL for the frontend),
then the frontend, then come back and lock CORS to the real Vercel domain.

---

## 1. Backend → Render

1. Go to <https://dashboard.render.com> → **New** → **Blueprint**.
2. Connect the GitHub repo **`anagharamadas/trialreads`**. Render detects
   [`render.yaml`](render.yaml) and proposes the **`trialreads-backend`** web service
   (root dir `backend`, build `pip install -r requirements.txt`, start
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`).
3. It will prompt for the secret env vars (marked `sync: false`). Paste the values
   from your local `backend/.env`:
   - `OPENAI_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `SUPABASE_JWT_SECRET`
   - `DATABASE_URL`  ← use the **Session pooler** URI (IPv4-friendly)
   - `GOOGLE_BOOKS_API_KEY`
   - `CORS_ORIGINS` → set to a placeholder for now (e.g. `https://example.com`);
     you'll update it after the frontend deploys.
   (`DEBUG=false`, `CORS_ALLOW_LOCALHOST=false`, `PYTHON_VERSION=3.12.9` are preset.)
4. **Create** the service. First build takes a few minutes.
5. When live, note the URL, e.g. `https://trialreads-backend.onrender.com`.
   Test it: open `https://<your-backend>.onrender.com/health` → `{"status":"ok"}`
   and `…/docs` for the Swagger UI.

> ⚠️ Render free tier **spins down after ~15 min idle**; the first request after
> that takes ~30–60s to wake. Fine for Phase 1.

---

## 2. Frontend → Vercel

1. Go to <https://vercel.com/new> → import **`anagharamadas/trialreads`**.
2. **Root Directory** → set to **`frontend`** (click Edit, choose the folder).
   Framework preset auto-detects **Next.js**.
3. Add **Environment Variables**:
   - `NEXT_PUBLIC_SUPABASE_URL` = your Supabase URL
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` = your Supabase publishable/anon key
   - `NEXT_PUBLIC_API_URL` = your Render backend URL from step 1
     (e.g. `https://trialreads-backend.onrender.com`) — **no trailing slash**
4. **Deploy**. When done you'll get a URL like `https://trialreads.vercel.app`.

---

## 3. Lock CORS to the Vercel domain

1. Back in **Render → your service → Environment**, set:
   - `CORS_ORIGINS` = your Vercel URL, e.g. `https://trialreads.vercel.app`
     (comma-separated if you have several, e.g. add the `*-git-main-*.vercel.app`
     preview domain too).
2. Save → Render redeploys. `CORS_ALLOW_LOCALHOST=false` is already set, so only the
   Vercel domain(s) can call the API from a browser.

---

## 4. Verify the deployed stack

- Open the **Vercel URL**, sign in, and walk the journey: shelf → add → summarise →
  recommend → chat → edit → delete. (Allow for the backend cold-start on the first call.)
- Confirm **HTTPS** on both URLs (Render + Vercel provision SSL automatically — just
  check the padlock).
- Supabase **Auth → URL Configuration**: add your Vercel URL to the allowed redirect/site
  URLs if you later enable email confirmation or OAuth.

---

## Notes

- Every push to `main` auto-deploys: Vercel rebuilds the frontend; Render rebuilds the
  backend.
- Secrets live only in the Render/Vercel dashboards and your local `.env` files — never
  in git.
- Hardening (spend limits, rate limits, monitoring, privacy policy) is Milestone 6.
