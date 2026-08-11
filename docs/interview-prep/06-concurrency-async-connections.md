# 06 — Concurrency, Async & Connection Management

## 1. The concept

Concurrency is doing multiple things in overlapping time. The engineering concerns:

- **Race conditions** — two operations interleave and corrupt shared state (the classic
  read-modify-write: two requests both read `count=5`, both write `6`, one increment is
  lost). Fixed with atomic operations, locks, or transactions with the right isolation.
- **Blocking vs. non-blocking / async I/O** — a thread waiting on network I/O is wasted.
  Async (event loop) or thread pools let one process handle many in-flight I/O-bound
  requests. **I/O-bound → concurrency helps; CPU-bound → you need parallelism (processes)
  because of the GIL in Python.**
- **Connection pooling** — opening a DB connection is expensive (TCP + TLS + auth), so
  you reuse a bounded pool. Pool size is a capacity/latency knob: too small → requests
  queue; too big → you exhaust the database's connection limit.
- **Idempotency & exactly-once** — under retries and concurrency, operations should be
  safe to repeat.
- **Bounded parallelism** — fan out work across a limited worker pool so you get speed
  without a thundering herd on a downstream dependency.

## 2. In TrialReads

**Request concurrency model.** FastAPI runs on Uvicorn; the route handlers here are
**synchronous** `def` functions, which FastAPI runs in a **thread pool** so blocking DB
and HTTP calls don't stall the event loop. This is a legitimate, common pattern —
sync handlers + threadpool — and it's why the code can use blocking psycopg2/httpx
without going fully async.

**Two connection strategies, on purpose** (see also section 05):

- **A shared pooled engine** for CRUD (`db.py`): `create_engine(url, pool_pre_ping=True,
  pool_size=5, max_overflow=5)`. Up to 10 connections are reused across requests.
  `pool_pre_ping=True` sends a cheap `SELECT 1` before handing out a connection, so a
  connection the DB silently dropped (idle timeout) is transparently replaced instead of
  erroring the request.
- **A per-request NullPool engine** for text-to-SQL (`library_query.py:_scoped_engine`).
  It deliberately does *not* pool, because each connection carries a specific user's
  `SET ROLE authenticated` + JWT claims; reusing one across users would leak identity. So
  it's created, used, `dispose()`d per request — trading connection-setup cost for
  correctness (isolation).

**The rate limiter is the race-condition set-piece** (`rate_limit.py:30-40`). A naive
implementation reads today's count, adds one, writes it back — a lost-update race under
concurrent requests. Instead it's a single **atomic upsert**:
```sql
INSERT INTO ai_usage (user_id, day, count) VALUES (:u, current_date, 1)
ON CONFLICT (user_id, day) DO UPDATE SET count = ai_usage.count + 1
RETURNING count;
```
The increment happens *inside the database* in one statement, so two simultaneous
requests can't lose an update — Postgres serializes the conflicting upserts on the
primary key. This is the textbook "make the read-modify-write atomic instead of locking
in the app" answer.

**Bounded parallelism in the agent's grounding** (`curation_agent.py:_ground`). Grounding
10 books sequentially cost ~15s (each book = a Google Books validate + a Hardcover rating
lookup, ~2s). They're independent, so they run on a `ThreadPoolExecutor(max_workers=6)` —
wall-clock becomes the slowest wave (~3–4s), not the sum. Two careful details:
- **Order preserved:** futures are collected in submission order, so the reading order the
  agent chose is kept.
- **`copy_context().run(...)`:** the parent's `contextvars` (which hold the active
  OpenTelemetry span) are copied into each worker, so per-item spans and the httpx
  auto-spans under them stay attached to the request trace instead of detaching. This is
  a subtle, senior-level correctness detail.
- **Bounded (6, not unbounded):** enough for two waves on a 10-item list, small enough not
  to hammer Google Books' flaky rate limit.

**Startup pool warming** (`main.py:_warm_db_pool`). On boot, one connection is opened and
a `SELECT 1` run, so the *first real request* doesn't pay the Supabase TLS/auth handshake
(measured 2.34s cold vs 0.78s warm). It's wrapped in try/except so a warm-up failure never
blocks the health check from coming up.

## 3. Gaps & upgrades to industry standard

- **Sync handlers + threadpool caps concurrency at the thread count.** Fully `async`
  handlers with an async driver (asyncpg, httpx async) scale I/O concurrency far higher on
  one process. The current model is simpler and fine at this scale, but it's the honest
  ceiling.
- **Pool size (5+5) is a guess, not measured.** Under real load you'd size it from the DB's
  `max_connections` ÷ instance count and p95 query time (Little's Law), and use a
  transaction-mode pooler (PgBouncer / Supabase pooler) so short queries share fewer
  physical connections.
- **Per-request `create_engine` for text-to-SQL is expensive.** A more advanced design
  keeps a pool of authenticated connections and sets/resets the role+claims on
  checkout/checkin — faster, but a reset bug reintroduces the cross-user leak, so it needs
  careful testing.
- **`ThreadPoolExecutor` per curate call** creates and tears down a pool each time; a shared
  bounded executor (or async gather with a semaphore) avoids the churn.
- **No distributed locking / coordination.** Not needed yet (the DB is the coordination
  point), but if background workers were added you'd reach for advisory locks or a queue's
  visibility timeout.

## 4. Ten interview questions & answers (framed around TrialReads)

**Q1. Your rate limiter increments a per-user daily counter. How do you avoid a lost
update under concurrent requests?**
A: I don't read-modify-write in the app — I do it atomically in the database with one
`INSERT … ON CONFLICT (user_id, day) DO UPDATE SET count = count + 1 RETURNING count`.
Postgres serializes conflicting upserts on the primary key, so two simultaneous requests
each get a correct, distinct count. No app-level lock, no race.

**Q2. Are your endpoints async? Why/why not, and what's the implication?**
A: The handlers are sync `def`, which FastAPI runs in a threadpool so blocking DB/HTTP
calls don't stall the event loop. It's simpler and lets me use blocking psycopg2/httpx.
The implication is that concurrency is bounded by the thread count; to scale I/O
concurrency much higher I'd move to fully async handlers with async drivers.

**Q3. Explain your two connection strategies and why they differ.**
A: CRUD uses a shared pooled engine (reuse connections, `pool_pre_ping` to skip dead
ones) because those queries are stateless and identical in privilege. Text-to-SQL uses a
*non-pooled* engine created per request, because each connection is stamped with a
specific user's role and JWT claims — reusing it across users would leak identity. So I
trade connection-setup cost for isolation correctness on that path only.

**Q4. What does `pool_pre_ping` do and what problem does it solve?**
A: It runs a cheap `SELECT 1` before lending a pooled connection. Databases and poolers
drop idle connections; without pre-ping the next request gets a dead connection and
errors. Pre-ping detects that and transparently replaces it, trading a tiny per-checkout
cost for reliability.

**Q5. The agent grounds 10 books. Walk me through making that fast and correct.**
A: The lookups are independent (each book: Google validate + Hardcover rating), so I fan
them out on a `ThreadPoolExecutor` with 6 workers — wall-clock drops from ~15s to ~3–4s.
I keep reading order by collecting futures in submission order, and I copy the parent
context (`contextvars`) into each worker so the OpenTelemetry spans stay attached to the
request trace. I bound at 6 workers so I don't hammer Google Books' rate limit.

**Q6. Why 6 workers and not 100?**
A: Bounded parallelism. The downstream (Google Books) is rate-limited and flaky, so an
unbounded fan-out would trigger 429s/503s — I'd go slower, not faster. Six covers a
10-item list in ~two waves while keeping the burst modest. The right number comes from the
downstream's limits and your latency target, not "as many as possible."

**Q7. I/O-bound vs CPU-bound — which is this workload, and how does that change your
approach?**
A: Almost entirely I/O-bound — waiting on Postgres, OpenAI, Google Books. So concurrency
(threads/async) is the lever; the GIL isn't the bottleneck because threads release it
during I/O. If I had CPU-bound work (say, local embeddings) I'd need multiprocessing or a
separate service, because Python threads can't run CPU work in parallel.

**Q8. What's the cold-start problem here and how did you mitigate it?**
A: Render's free tier spins the instance down when idle; the first request after wake pays
the process start plus, historically, the DB TLS/auth handshake (2.34s vs 0.78s warm). I
warm the pool at startup with a `SELECT 1` so the first real query is fast, and I expose
`uptime_seconds` on `/health` so cold starts are visible in dashboards instead of silently
inflating latency percentiles.

**Q9. How would you size the connection pool for production?**
A: From the database's `max_connections`, divided across instances, leaving headroom —
then validate against p95 query time and target throughput (Little's Law: concurrency =
arrival rate × service time). I'd also front Postgres with a transaction-mode pooler so
many short queries multiplex over fewer physical connections, which is how you avoid
exhausting Postgres' connection limit as instances scale.

**Q10. Where could a race condition still exist in this system, and how would you handle
it?**
A: `POST /library` has no uniqueness constraint, so two concurrent identical adds create
two rows — a benign duplicate, not corruption. If that mattered I'd add a unique index (like
shelves have) plus `ON CONFLICT`, or an idempotency key. The reorder feature swaps two
`reading_order` values in one transaction, which is safe under Read Committed; if I needed
strict ordering under heavy concurrent reorders I'd use `SELECT … FOR UPDATE` or serialize
via a single positional column with careful transactions.

---

### Follow-ups interviewers love here
- "What isolation level?" → Postgres default **Read Committed**; the upsert doesn't need
  more because it's a single atomic statement.
- "async vs threads in Python?" → both give concurrency for I/O; async is more
  memory-efficient at high connection counts; threads are simpler and fine here.
- "What if two workers hit Google Books' rate limit?" → the `google_books.search` retry
  with backoff (section 07) absorbs transient 503s; bounded workers keep the burst under
  the limit.
