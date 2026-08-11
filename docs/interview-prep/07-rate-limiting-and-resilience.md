# 07 — Rate Limiting & Resilience

## 1. The concept

**Rate limiting** caps how much a client can do in a window — to control cost, protect
capacity, and blunt abuse/DoS. Algorithms range from **fixed window** (simple, but bursty
at boundaries), **sliding window**, **token bucket** (allows bursts up to a cap, refills
steadily — the industry default), to **leaky bucket**. It must be *shared state* if you
run multiple instances (a per-process counter under-counts), and it should tell the client
how to back off (`429` + `Retry-After`).

**Resilience** is staying correct/available when dependencies misbehave: **timeouts** (never
wait forever), **retries with backoff + jitter** (absorb transient failures without a
thundering herd), **circuit breakers** (stop hammering a dead dependency), **graceful
degradation** (partial results beat an error), and **bulkheads** (isolate failures so one
slow dependency doesn't sink everything). The golden rule: **only retry idempotent
operations**, or you double-apply side effects.

## 2. In TrialReads

**Rate limiting (cost control on the only paid resource).** The three AI endpoints
(`/summarise`, `/recommend`, `/library/query`) and `/curate` are the only things that cost
money (OpenAI tokens). A per-user **daily cap** (`daily_ai_limit`, default 50) is enforced
by `enforce_daily_limit` (`rate_limit.py`):

- It's a **fixed-window** limiter keyed on `(user_id, day)` in the `ai_usage` table.
- It's **shared state in Postgres**, not process memory — deliberately, so it survives
  Render's cold-start restarts and is consistent across instances (a per-process counter
  would reset on every spin-up and under-count with multiple instances).
- The increment is the **atomic upsert** from section 06 (no lost updates).
- Over the cap → **HTTP 429** with a human-readable detail.
- **Ordering as a cost guard:** `/curate` runs the shelf-ownership check *before*
  `enforce_daily_limit`, so probing another user's shelf 404s *without* consuming the
  prober's quota or running paid inference (`routers/shelves.py:266-269`). Rate limiting
  and authorization composed in the right order.

**Defense-in-depth on spend.** The app-level cap is backed by an **OpenAI account spend
limit** set in the provider dashboard — so even a bug that bypassed the app limit can't run
up an unbounded bill. Two independent controls.

**Resilience patterns present:**

- **Retry with backoff** on Google Books (`google_books.py:20-35`): it 503s
  stochastically, so `search()` retries twice with a 0.4s sleep between — "one retry halves
  the drop rate." Reads are idempotent, so retrying is safe.
- **Graceful degradation in the agent** (`curation_agent.py`): a book Google Books can't
  confirm is *dropped*, not invented (grounding), and if too few survive, the agent proposes
  a shorter list and says so — a partial, honest result instead of a failure or a
  hallucination. Ratings are best-effort: if Hardcover has no rating, the book still ships
  without one.
- **Never let observability break a request** (`llm_observability.py`): the Langfuse
  callback import is wrapped in try/except so a monitoring failure can't fail a paid user
  request. Same instinct in `main.py`'s warm-up (failure never blocks startup) and the
  Sentry/OTel no-op-when-unconfigured design.
- **Health checks** (`/health`) let Render restart an unhealthy instance and let synthetic
  monitors alert on downtime.

## 3. Gaps & upgrades to industry standard

- **Fixed window, not token bucket.** A daily fixed window allows a burst of 50 in one
  second at midnight. A token bucket (e.g., 50/day refilling continuously, or a per-minute
  sub-limit) smooths bursts and is the industry default. Also there's only a *daily* cap —
  no per-minute limit to stop a rapid burst, and **no global limit** to protect total spend
  across all users.
- **No `Retry-After` / `X-RateLimit-*` headers** on the 429, so clients can't back off
  precisely (section 03).
- **No timeouts on OpenAI calls** shown — httpx has defaults, but an explicit per-call
  timeout + a **circuit breaker** would stop a slow/incident-y provider from tying up
  threads. This is the biggest resilience gap: a hung LLM call currently blocks a worker
  for its full duration.
- **Retries lack jitter** and cover only Google Books, not OpenAI. Backoff should be
  exponential with jitter to avoid synchronized retry storms.
- **No idempotency keys**, so the non-idempotent POST creates can't be safely retried by
  the client (section 03).
- **Rate limiting is per-user only.** No per-IP limit for unauthenticated abuse (though all
  AI routes require auth, which mitigates it) and no WAF/edge protection.

## 4. Ten interview questions & answers (framed around TrialReads)

**Q1. How does your rate limiter work and where does the state live?**
A: A per-user, per-day fixed-window counter in a Postgres table `ai_usage`, incremented
atomically with an upsert and returning the new count; over the daily cap → 429. State is
in Postgres, not process memory, on purpose — so it survives restarts and is shared across
instances. A per-process counter would reset on every cold start and under-count with
multiple instances.

**Q2. Why fixed window and what's the downside? What would you use instead?**
A: Fixed window is simple and the daily granularity fits "N free AI calls a day." The
downside is boundary bursts — a user could spend the whole day's allowance in one second.
I'd add a token bucket (or a per-minute sub-limit) to smooth bursts; token bucket is the
industry default because it permits controlled bursts while bounding the sustained rate.

**Q3. You run multiple instances (in principle). Why can't the limiter be in-memory?**
A: Two reasons: each instance would have its own counter, so the real limit becomes
N×cap; and a restart (Render cold start) would reset it. Shared state — Postgres here,
Redis at higher throughput — is required for a correct distributed limit.

**Q4. A rate-limit check is itself a write under concurrency. Any race?**
A: No — it's a single atomic `INSERT … ON CONFLICT DO UPDATE … RETURNING count`, so
concurrent requests can't lose an increment. If I'd done read-then-write in the app I'd
have a lost-update race; pushing the read-modify-write into one SQL statement removes it.

**Q5. Your `/curate` endpoint checks ownership before the rate limit. Why does order
matter?**
A: Because inference costs money and quota. If I incremented the counter first, an attacker
probing random shelf ids would burn a victim's quota and I'd pay for nothing. Checking
ownership first means a probe 404s with zero cost — authorization gates the expensive work.

**Q6. How do you protect against runaway OpenAI cost beyond the app limit?**
A: Defense in depth — the app's per-user daily cap plus an OpenAI *account* spend limit set
in their dashboard. Independent controls, so a bug that bypassed one is still bounded by the
other. I'd add a global daily budget in the app too, since today the cap is per-user only.

**Q7. Google Books is flaky. How do you stay resilient?**
A: `search()` retries twice with a short delay because Google Books 503s stochastically —
and reads are idempotent so retrying is safe. In the agent, any book I can't validate is
dropped rather than invented, so a partial-but-correct list ships instead of a failure or a
hallucination. I'd upgrade the retry to exponential backoff with jitter and add a circuit
breaker.

**Q8. What's a circuit breaker and where would it help here?**
A: It tracks failures to a dependency and, past a threshold, "opens" — short-circuiting
calls for a cooldown so you stop hammering a dead service and failing slowly. The biggest
place it'd help is OpenAI: during an outage, requests currently block a worker for the full
timeout; a breaker would fail fast, shed load, and recover automatically.

**Q9. Which operations are safe to retry and which aren't?**
A: Idempotent ones — GETs, the Google Books reads, the bulk add (`ON CONFLICT DO NOTHING`).
Not safe: `POST /library` (a retry after a lost 201 creates a duplicate, since there's no
uniqueness constraint) and the rate-limit increment itself (a blind retry would double-count).
The fix for the POSTs is an idempotency key; the increment is already inside a transaction so
it's atomic per request.

**Q10. Give me your graceful-degradation story.**
A: The agent's core promise is "every book is real." So when grounding can't verify a
proposed book, I drop it; if that leaves too few, the agent proposes a shorter list and
says so honestly. Ratings are best-effort — no rating just means no stars. And observability
failures are swallowed so monitoring can never break a paid request. The system prefers a
smaller correct answer over a bigger wrong one.

---

### Follow-ups interviewers love here
- "Token bucket math?" → capacity = max burst, refill rate = sustained limit; a request
  needs ≥1 token or it's 429'd.
- "Where would Redis fit?" → an atomic `INCR` with `EXPIRE`, or a Lua script for token
  bucket, when Postgres write volume for counters gets high.
- "Retry storms?" → exponential backoff **with jitter** so clients don't synchronize and
  re-DoS the recovering service.
