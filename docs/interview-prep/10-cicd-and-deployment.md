# 10 — CI/CD & Deployment (Infrastructure-as-Code, 12-Factor)

## 1. The concept

**CI (Continuous Integration)** = every change is automatically built and tested on merge,
so integration problems surface immediately. **CD (Continuous Delivery/Deployment)** = every
green change is automatically shippable/shipped. The engineering ideas:

- **Build once, promote the artifact** — same artifact through environments; config, not
  code, changes between them.
- **The 12-Factor App** — config in the environment (never in code), strict separation of
  build/release/run, stateless processes, dev/prod parity, treat logs as event streams.
- **Infrastructure-as-Code (IaC)** — infrastructure defined in versioned files (Terraform,
  a Render Blueprint, a Vercel config) so environments are reproducible and reviewable, not
  clicked together by hand.
- **Deployment strategies** — rolling, blue-green, canary; and **rollback** as a first-class
  operation.
- **Secrets management** — secrets never in git; injected at runtime.
- **Environments & parity** — local ≈ preview ≈ production, so "works on my machine" holds.
- **Health checks & zero-downtime** — the platform only routes to healthy instances and
  drains old ones on deploy.

## 2. In TrialReads

**Two independently-deployed artifacts from one monorepo**, both auto-deploying on push to
`main` (this *is* continuous deployment):

- **Backend → Render**, defined as **IaC** in [`render.yaml`](../../render.yaml) — a Render
  **Blueprint**. It declares the service (`runtime: python`, `rootDir: backend`, build =
  `pip install -r requirements.txt`, start = `uvicorn app.main:app --host 0.0.0.0 --port
  $PORT`), a `healthCheckPath: /health`, and every env var. This is reproducible
  infrastructure — "New → Blueprint" recreates the whole service — not dashboard clicking.
- **Frontend → Vercel**, root directory `frontend/`, auto-detected Next.js, env vars in the
  Vercel dashboard, deploy previews per push.

**12-Factor in practice:**
- **Config in the environment.** All settings come from env vars via typed `Settings`
  (`config.py`), and the Blueprint marks every secret `sync: false` so Render *prompts* for
  it in the dashboard and it's never in git. Local dev uses a gitignored `.env`. The frontend
  only ever gets `NEXT_PUBLIC_*` values (no secret can reach the browser).
- **Dev/prod parity via config, not code.** The exact same code runs locally and in prod;
  behavior differs only by env (e.g., `CORS_ALLOW_LOCALHOST=false`, `DEBUG=false`,
  `DEPLOYMENT_ENVIRONMENT=production` in the Blueprint). The OTel pipeline is identical code
  for local Jaeger vs. Grafana Cloud — a pure config swap (section 09).
- **Logs as event streams.** Structured JSON to stdout; Render captures it. No log files.
- **Stateless processes / release management.** Stateless backend (section 01); Render/Vercel
  handle rolling deploys and only route to healthy instances (`/health`).

**A real incident that teaches deployment tooling.** Vercel blocked every Phase-2 deploy
because commits were authored with an email not linked to the GitHub account (an anti-abuse
guard) — so the *backend* auto-deployed while the *frontend* silently froze. The fix was to
set the correct commit-author email and push. Lesson: CD platforms have guardrails that can
silently no-op; you diagnose by checking the platform's Deployments tab (state: old vs.
building vs. error), not by guessing.

**Rollback** is Git-native: revert the commit (auto-redeploys) or, in the Vercel/Render UI,
promote a previous known-good deployment.

## 3. Gaps & upgrades to industry standard

- **No CI pipeline / no automated tests gate.** This is the biggest gap: pushes deploy
  straight to prod with **no build/test/lint gate**. Industry standard is GitHub Actions that
  runs `pytest`, type-checks, lints, and builds on every PR, and only merges/deploys if green.
  (There are currently no automated tests in the repo at all — a documented gap; verification
  has been manual + scripted.)
- **No staging environment.** `main` → production directly. A staging/preview environment for
  the *backend* (Vercel gives frontend previews already) would let you test a release before
  prod.
- **No canary/blue-green.** Deploys are rolling replace. For a high-traffic service you'd
  canary a % of traffic and auto-rollback on error-rate regression.
- **DB migrations aren't in the pipeline.** Schema SQL is hand-run against Supabase, decoupled
  from the app deploy — so code and schema can drift. A migration tool run as a release step
  (before the new app boots) is the fix (section 02).
- **Secrets are platform env vars, not a managed vault** with rotation/audit — fine at this
  scale, upgrade at org scale.
- **No dependency/security scanning** (Dependabot, `pip-audit`, SBOM) in CI.

## 4. Ten interview questions & answers (framed around TrialReads)

**Q1. Walk me through what happens from `git push` to live.**
A: Push to `main` → Render sees a change under `backend/`, runs the Blueprint's build
(`pip install`), then the start command, health-checks `/health`, and routes traffic when
healthy; Vercel independently builds `frontend/` and promotes it. Two artifacts, independent
deploys, from one monorepo — continuous deployment. The honest gap: there's no CI test gate
between push and deploy.

**Q2. What's Infrastructure-as-Code and where do you use it?**
A: Infrastructure defined in versioned files instead of dashboard clicks, so it's
reproducible and reviewable. My backend is a Render Blueprint (`render.yaml`) declaring the
service, build/start commands, health check, and env var names. Anyone can recreate the
service from the repo. Terraform is the heavier, cloud-agnostic version of the same idea.

**Q3. How do you manage secrets across environments?**
A: Never in git. Config comes from env vars via typed settings; the Blueprint marks secrets
`sync: false` so Render prompts for them in the dashboard, and local dev uses a gitignored
`.env`. The frontend only receives `NEXT_PUBLIC_*` values, so no secret (OpenAI key, service
role) can reach the browser — I've verified the bundle contains none.

**Q4. Explain a couple of 12-Factor principles you actually follow.**
A: (1) Config in the environment — same code, behavior varies only by env vars (CORS lock,
debug, telemetry endpoint), so I never rebuild to change environments. (2) Logs as event
streams — structured JSON to stdout, captured by the platform, no log files. (3) Stateless
processes — no session/local state, so instances are disposable and horizontally scalable.

**Q5. You had a deploy silently fail. What happened and how did you debug it?**
A: Vercel blocked deploys because the commits' author email wasn't linked to the GitHub
account — an anti-abuse guard. The backend (Render, no such check) kept deploying, so only the
frontend froze, which looked like "my changes vanished." I diagnosed it in Vercel's
Deployments tab — the latest deploy showed a blocked state with the reason — set the correct
git author email, and pushed. Lesson: check the platform's deploy log; don't assume push =
deploy.

**Q6. How do you roll back a bad deploy?**
A: Git-native — revert the commit and it auto-redeploys the previous state; or in the
platform UI, promote the last known-good deployment instantly. Because deploys are
immutable artifacts, rollback is just pointing traffic at a prior one. I'd pair this with an
alert (section 09) so a regression triggers rollback quickly.

**Q7. What would your CI pipeline look like, concretely?**
A: GitHub Actions on every PR: install deps, run `pytest` (unit + the two-account isolation
tests), `mypy`/type-check, `ruff`/lint, and `npm run build` + typecheck for the frontend;
plus `pip-audit`/Dependabot for vulnerable deps. Branch protection requires it green to
merge. Then deploy runs migrations and ships. Today none of that gate exists — it's my top
upgrade.

**Q8. Your schema changes are run by hand. Why is that risky in a deploy pipeline?**
A: Because code and schema can drift — the app can deploy expecting a column the DB doesn't
have yet, or vice versa. The fix is a migration tool (Alembic) whose migrations run as a
release step *before* the new app boots, versioned in the same repo, with the expand/contract
pattern for zero-downtime changes so old and new app versions coexist during the rollout.

**Q9. Canary vs blue-green vs rolling — which would you add and why?**
A: For this scale, rolling (what Render does) is fine. As traffic grows I'd add **canary** —
route a small % to the new version, watch error rate and latency (I already have RED
metrics), and auto-rollback on regression. Blue-green (two full environments, flip traffic)
gives instant rollback but doubles infra; canary is cheaper and catches regressions on real
traffic gradually.

**Q10. How do you ensure dev/prod parity?**
A: Same code path everywhere; only env vars differ. The telemetry pipeline is literally the
same code for local Jaeger and Grafana Cloud. Vercel gives per-PR preview deployments that
mirror prod. The gap is a backend staging environment — right now `main` goes straight to
backend prod, so I'd add one before high-stakes changes.

---

### Follow-ups interviewers love here
- "Where do migrations run — before or after the app deploys?" → before, as a release step,
  with backward-compatible (expand/contract) changes.
- "How do you test a deploy didn't break prod?" → health check + smoke tests + watch RED
  metrics/alerts; auto-rollback on regression.
- "Monorepo CI cost?" → path-filter jobs so a frontend-only change doesn't run the backend
  suite.
