# 01 — System Architecture & Design

## 1. The concept

System design is deciding how to split a system into components, how those components
talk, where state lives, and how the whole thing scales and fails gracefully. At the
"design a system" round, interviewers look for: a clear component decomposition,
sensible **boundaries** (what each part owns), **statelessness** where it enables
scaling, an understanding of the **data flow** and where the **bottlenecks** are, and
honest **trade-off** reasoning (latency vs. cost vs. complexity vs. consistency).

Key vocabulary: **tiers** (presentation / application / data), **stateless vs.
stateful** services, **horizontal vs. vertical** scaling, **synchronous vs.
asynchronous** work, **coupling/cohesion**, and the idea that you scale the part that's
actually the bottleneck — not everything.

## 2. In TrialReads

TrialReads is a classic **three-tier architecture** with a clean split of
responsibilities:

- **Presentation tier — Next.js on Vercel.** The frontend (`frontend/`) is a React
  App-Router app served from Vercel's edge/CDN. It holds *no secrets* and talks to the
  backend over HTTPS with the user's JWT.
- **Application tier — FastAPI on Render.** The backend (`backend/app/`) is a
  **stateless** Python service. It owns all business logic, the only OpenAI key, and
  all privileged database access. Statelessness is deliberate and load-bearing:
  - No session store — auth is a self-contained JWT verified per request (section 04).
  - Chat history lives in the *client* and is sent on each turn (the curation agent and
    text-to-SQL both take the full history as input), so any instance can serve any
    request. This is what lets Render add instances without sticky sessions.
  - The one piece of cross-request state — the daily rate-limit counter — is pushed
    into Postgres (`ai_usage`), not process memory, precisely so it survives restarts
    and is shared across instances (section 07).
- **Data / identity tier — Supabase.** Managed Postgres (data), Supabase Auth
  (identity/JWT issuance), and RLS (tenant isolation).
- **External services (dependencies, not owned):** OpenAI (LLM), Google Books
  (grounding + covers), Hardcover (ratings), Amazon (link target only). Each is reached
  over HTTPS from the backend; the frontend never calls them directly.

**Repository shape.** A **monorepo** (`backend/`, `frontend/`, `supabase/`, `docs/`).
One repo, two independently-deployed artifacts (Render watches `backend/`, Vercel
watches `frontend/`). This keeps a single source of truth and atomic cross-cutting
changes while allowing independent deploy cadences.

**Data-flow example (a library question):** browser → `POST /library/query` with JWT
→ FastAPI verifies JWT → checks rate limit → condenses the follow-up into a standalone
question (1 LLM call) → LlamaIndex generates SQL (1 LLM call) → executes on an
RLS-scoped connection → synthesizes an answer (1 LLM call) → JSON back to the browser.
Three OpenAI round-trips is the latency story — a great thing to be able to diagram.

**Where the bottlenecks actually are.** Not CPU or the DB — it's the **external LLM
calls** (seconds each) and Render's **free-tier cold start** (~30–60s after idle). The
design reflects this: `/health` reports `uptime_seconds` to make cold starts visible,
the DB pool is warmed at startup, and grounding lookups run concurrently (sections
06/09). That's the senior move — optimize the real bottleneck, not an imagined one.

## 3. Gaps & upgrades to industry standard

- **No async job queue.** The curation agent and summaries are synchronous
  request/response, which is why the client waits 10–60s. A production design pushes
  long LLM work onto a queue (SQS/Celery/Cloud Tasks) and returns a job id the client
  polls or receives via WebSocket/SSE. This also survives the request timeout and lets
  you retry.
- **Free-tier single instance, no autoscaling / load balancer.** Fine for a portfolio;
  at scale you'd run N stateless instances behind a load balancer (the statelessness is
  already there to allow it) with health-check-based autoscaling.
- **No caching tier.** Cover lookups, Google Books results, and even summaries are
  recomputed every time. A Redis/CDN cache is the obvious next layer (your Phase-4
  list).
- **No API gateway / BFF.** The browser calls the FastAPI service directly. A larger
  system often adds an edge gateway (auth, rate limiting, routing) or a
  backend-for-frontend.
- **Single region.** One Render region, one Supabase region. Multi-region/read-replica
  is a later scaling and latency concern.

## 4. Ten interview questions & answers (framed around TrialReads)

**Q1. Draw and walk me through your architecture.**
A: Three tiers. Next.js on Vercel (presentation, no secrets), a stateless FastAPI
service on Render (application logic + the only privileged credentials), and Supabase
Postgres + Auth (data + identity). The frontend talks only to my backend over HTTPS
with a JWT; the backend fans out to OpenAI, Google Books, and Hardcover. Two deploy
targets from one monorepo.

**Q2. Why is the backend stateless, and what did you do to keep it that way?**
A: Stateless means any instance can serve any request, which is what lets you scale
horizontally behind a load balancer without sticky sessions. I keep it stateless by
(a) using self-contained JWTs instead of server sessions, (b) keeping chat history on
the client and sending it each turn, and (c) putting the only shared mutable state —
the rate-limit counter — in Postgres, not process memory.

**Q3. Where's the bottleneck in a request, and how did you address it?**
A: Not the DB or CPU — it's the external LLM calls (seconds each) and Render's cold
start after idle. So I optimize *those*: warm the DB pool at startup so the first query
doesn't pay the TLS handshake, run the agent's grounding lookups concurrently instead
of sequentially (~15s → ~3s), and expose `uptime_seconds` on `/health` so cold starts
are visible in monitoring rather than silently polluting latency percentiles.

**Q4. The curation agent takes 30–60s. That's a bad UX. Redesign it.**
A: Make it asynchronous. `POST /curate` enqueues a job and returns a job id immediately;
a worker runs the agent and grounding; the client gets the result via SSE/WebSocket or
by polling `GET /jobs/{id}`. That removes the request-timeout risk, lets me retry on
failure, and frees the web tier. I'd show a live "thinking" state and stream partial
progress. For now it's synchronous with a thinking indicator + retry, which is the
pragmatic Phase-1/2 choice.

**Q5. Monorepo vs. polyrepo — why did you choose monorepo, and what are the
downsides?**
A: Monorepo gives one source of truth, atomic cross-cutting changes (e.g., change an
API contract and its client in one commit), and simpler dependency visibility. Render
and Vercel each watch their subdirectory, so deploys stay independent. Downsides at
scale: CI must be path-filtered so unrelated changes don't rebuild everything, and
access control is coarser. For two tightly-coupled artifacts, monorepo wins.

**Q6. How would you scale this to 1M daily users?**
A: The web tier is already stateless, so: N instances behind a load balancer with
autoscaling; move LLM work to a queue with workers scaled separately (it's the
expensive, slow part); add Redis for caching covers/summaries and a CDN for static
covers; add Postgres read replicas for the read-heavy list endpoints and connection
pooling (PgBouncer); and cap cost with per-user and global rate limits plus provider
spend limits. Data isolation (RLS) already holds per-row; at extreme scale I'd consider
tenant sharding.

**Q7. What happens if OpenAI (or Google Books) is down or slow?**
A: Today: the summarise/recommend/curate calls fail and surface an error with a retry;
Google Books already retries transient 503s, and the agent drops books it can't ground
rather than inventing them (graceful degradation). Better: timeouts + circuit breakers
so a slow provider doesn't tie up workers, cached fallbacks, and the async queue so a
provider blip retries instead of failing the user.

**Q8. Why does the frontend never call OpenAI/Google directly?**
A: Two reasons. Security — the OpenAI key must live only on the backend; a browser call
would expose it (I even grep the frontend bundle in CI-style checks to confirm no
secret leaks). And control — routing through the backend lets me authenticate,
rate-limit, ground, and observe every call in one place.

**Q9. What are the failure domains, and what's your single point of failure?**
A: Failure domains: Vercel (frontend), Render (backend), Supabase (data+auth), and each
external API. SPOFs are Render (single instance/region on free tier) and Supabase (one
primary). The frontend degrades to a "can't reach API" state rather than a blank page.
To harden: multi-instance backend, Supabase read replicas / PITR backups, and
provider-agnostic abstractions so a dependency can be swapped.

**Q10. If you started over, what would you change architecturally?**
A: Introduce the async job queue for LLM work from day one, add a caching layer, and
standardize the data model (one PK strategy, a real migration tool). I'd also add an
abstraction over the LLM provider so I'm not coupled to OpenAI, and put an API
schema/contract (OpenAPI is already generated by FastAPI) under contract tests shared
with the frontend types.

---

### Follow-ups interviewers love here
- "Sync vs async — where's the line?" → user-facing sub-second reads stay sync;
  anything multi-second or externally-dependent goes async.
- "CAP theorem here?" → single-primary Postgres favors consistency; you'd trade toward
  availability with replicas + read-your-writes handling.
- "Cost model?" → the only variable cost is LLM tokens; that's why rate limits, spend
  caps, and caching are architectural, not afterthoughts.
