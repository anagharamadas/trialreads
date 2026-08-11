# 02 — Relational Databases & Data Modeling

## 1. The concept

A relational database stores data as **tables** (relations) of typed rows, with
relationships expressed by **keys**. The engineering skill is *data modeling*:
choosing tables, columns, keys, and constraints so that the data is (a) correct by
construction, (b) efficient to query for your access patterns, and (c) able to
evolve. The recurring themes interviewers probe:

- **Keys & referential integrity** — primary keys (unique row identity), foreign
  keys (relationships), and what happens on delete (`CASCADE`, `SET NULL`, `RESTRICT`).
- **Normalization vs. denormalization** — normalize to remove redundancy and update
  anomalies; *deliberately* denormalize when a read pattern or a security rule makes a
  join expensive or fragile. Know *why* you'd do either.
- **Constraints** — `NOT NULL`, `CHECK`, `UNIQUE`. Push invariants into the database
  so no application bug can violate them.
- **Indexing** — an index trades write cost + storage for read speed. You index the
  columns you filter/join/sort on. Composite index column order matters.
- **Transactions & ACID** — a transaction is all-or-nothing (atomic), leaves the DB
  valid (consistent), is isolated from concurrent ones, and survives crashes (durable).
- **Query performance** — the **N+1 problem**, `EXPLAIN`/query plans, and using joins
  or aggregation instead of loops.

## 2. In TrialReads

The data layer is **Supabase Postgres**. Schema lives in
[`supabase/schema.sql`](../../supabase/schema.sql) and
[`supabase/shelves.sql`](../../supabase/shelves.sql); it's applied as idempotent SQL
migrations (`create table if not exists`, `drop policy if exists … create policy`).

**Core tables**

- `library` — a user's books. `id bigint generated always as identity primary key`,
  `user_id uuid not null references auth.users(id) on delete cascade`, and a
  **`CHECK` constraint** pinning `status` to the four legal values and `year` to a
  sane range. So an invalid status can't exist *at the database level*, regardless of
  application bugs. (`schema.sql:13-23`)
- `shelves` / `shelf_books` — Goodreads-style collections (a "shelf" is a tag) and
  their items. (`shelves.sql:17-46`)
- `ai_usage` — a per-user, per-day counter for rate limiting, keyed on
  `primary key (user_id, day)`. (`schema.sql:78-83`)

**Modeling decisions worth defending in an interview**

- **A deliberate denormalization:** `shelf_books.user_id` is stored even though it's
  derivable via `shelf_id → shelves.user_id`. The reason is *security, not
  performance*: it lets the RLS policy be a plain `user_id = auth.uid()` check with no
  join (`shelves.sql:29-30, 86-89`). Simpler policies are easier to get provably
  correct — the join version is where subtle isolation bugs hide.
- **Nullable FK with `ON DELETE SET NULL`:** `shelf_books.library_book_id` optionally
  links a shelf entry to an owned book. The agent recommends books you don't own, so
  the link *must* be optional; and if the owned book is later deleted, the shelf entry
  survives with the link nulled (`shelves.sql:37`). Contrast with `user_id … ON DELETE
  CASCADE` — deleting a user should erase their data.
- **`UNIQUE` with `NULLS NOT DISTINCT`:** `unique (shelf_id, title, author) nulls not
  distinct` prevents duplicate books on a shelf *including* two entries with the same
  title and a NULL author (Postgres 15+ semantics). This is what makes the bulk-insert
  "skip duplicates" behavior correct (`shelves.sql:50-51`).

**Indexing.** Every table is filtered by `user_id`, so each has a `user_id` index
(`schema.sql:26`, `shelves.sql:53`). `shelf_books` also has a composite
`(shelf_id, reading_order)` index (`shelves.sql:54-55`) matching the shelf-detail
query, which filters by `shelf_id` and orders by `reading_order`.

**No N+1.** The shelves list needs a per-shelf book count. Instead of one query per
shelf, it's a single `LEFT JOIN … GROUP BY`:
[`routers/shelves.py:70-82`](../../backend/app/routers/shelves.py). This is the
canonical N+1 talking point — I can show the loop I *didn't* write.

**Transactions.** Multi-statement work uses `with engine.begin()` (a transaction):
the shelf update recomputes the book count in the same transaction
(`shelves.py:109-124`), and the bulk insert adds N books atomically — either all
non-duplicate rows land or none do (`shelves.py:200-224`). The `ai_usage` increment
is a single atomic `INSERT … ON CONFLICT DO UPDATE … RETURNING count` (an **upsert**),
which is also the concurrency story — see section 06.

**Views as an abstraction/security boundary.** `my_library` is a view that projects
`library` minus `user_id` and self-filters to `auth.uid()` — used by the text-to-SQL
feature (`schema.sql:67-73`). Covered in depth in section 05.

## 3. Gaps & upgrades to industry standard

- **No migration tool.** Schema is hand-run `.sql`. Industry standard is a versioned
  migration framework (**Alembic**, or Supabase's migration CLI) with an ordered,
  checksummed history and rollback. Right now there's no record of *which* migrations
  ran against prod. **This is the #1 upgrade.**
- **No pagination.** `GET /library` and `GET /shelves/{id}/books` return the full set.
  Fine for tens–hundreds of rows; at scale you need keyset (cursor) pagination and a
  `LIMIT`. (This is on your Phase-4 list.)
- **`bigint identity` PK for `library` vs. `uuid` for shelves.** Inconsistent. `bigint`
  is compact and sequential (good for index locality) but enumerable/guessable; `uuid`
  is opaque and shard-friendly but larger. A real system picks one policy; UUIDv7
  (time-ordered) is the modern "best of both."
- **No read replicas / connection pooler tuning.** Single primary; `pool_size=5`. At
  scale you'd add read replicas for read-heavy endpoints and use a transaction-mode
  pooler (PgBouncer / Supabase's) sized to the workload.
- **No `EXPLAIN ANALYZE` in CI.** Query plans aren't tracked, so a future index
  regression would be invisible until it's slow in prod.
- **Bulk insert is a row-by-row loop** (`shelves.py:202-221`) inside one transaction —
  correct, but a single multi-row `INSERT … VALUES (…), (…)` would be one round-trip
  instead of N. Fine at N≤10; worth noting.

## 4. Ten interview questions & answers (framed around TrialReads)

**Q1. Walk me through your schema and why you modeled it this way.**
A: Three user-owned entities — `library`, `shelves`, `shelf_books` — plus an
`ai_usage` counter. Everything roots at `auth.users` via a `user_id` FK with
`ON DELETE CASCADE`, so deleting a user erases their data. `library` uses a `bigint`
identity PK; shelves use UUIDs. Books belong to shelves via `shelf_id` (cascade
delete), and can *optionally* link back to an owned library row via a nullable
`library_book_id`. Correctness invariants — legal `status` values, one book per shelf —
live in `CHECK` and `UNIQUE` constraints, not application code.

**Q2. Why did you denormalize `user_id` onto `shelf_books` when it's derivable from
`shelf_id`?**
A: For security correctness, not performance. It lets the row-level-security policy be
`user_id = auth.uid()` — a single-column check with no join. The alternative, joining
to `shelves` to derive the owner in every policy, is where subtle isolation bugs live.
I accept the redundancy (kept consistent because the API always sets `user_id` from
the JWT) to make the security rule trivially auditable.

**Q3. What's the N+1 query problem and where could it have bitten you here?**
A: N+1 is issuing one query to get N parents and then one query *per parent* for its
children — N+1 round-trips. It would've bitten the shelves list, which shows a book
count per shelf. Instead of looping shelves and counting each, I do one
`LEFT JOIN shelf_books … GROUP BY shelf.id` — a single query. `LEFT` (not inner) so
empty shelves still return with count 0.

**Q4. How do you guarantee a book can't appear twice on the same shelf, even with a
NULL author?**
A: A unique index on `(shelf_id, title, author)` with `NULLS NOT DISTINCT`. By default
Postgres treats NULLs as distinct, so two "same title, no author" rows would both be
allowed; `NULLS NOT DISTINCT` (PG15+) makes them collide. The bulk-add then uses
`INSERT … ON CONFLICT (shelf_id, title, author) DO NOTHING` so duplicates are silently
skipped instead of erroring.

**Q5. Explain `ON DELETE CASCADE` vs `SET NULL` and where you used each and why.**
A: `CASCADE` deletes children when the parent goes — used for `user_id` (delete user →
delete their rows) and `shelf_id` (delete shelf → delete its books). `SET NULL` keeps
the child but clears the link — used for `library_book_id`, because a shelf entry
recommended by the agent should survive even if I later delete the owned copy from my
library; it just loses the "in your library" link.

**Q6. Which indexes did you create and how did you decide?**
A: I index what I filter, join, and sort on. Every table is always filtered by
`user_id`, so each has a `user_id` index. `shelf_books` additionally has a composite
`(shelf_id, reading_order)` index because the shelf-detail query filters by `shelf_id`
and orders by `reading_order` — a composite in that column order lets Postgres satisfy
both from the index. I'd validate with `EXPLAIN ANALYZE` before trusting it.

**Q7. Your bulk "accept these books" endpoint — is it atomic? What if one row
violates the unique constraint?**
A: It runs inside `with engine.begin()`, a single transaction. Each row is
`INSERT … ON CONFLICT DO NOTHING`, so a duplicate doesn't raise — it just inserts zero
rows and is skipped. Non-duplicates all commit together; if any *non-conflict* error
occurred, the whole transaction rolls back, so I never end up with a half-added list.

**Q8. How would you add pagination to `GET /library` at scale?**
A: Keyset (cursor) pagination, not `OFFSET`. `OFFSET` scans and discards, so page 10000
is slow. Instead order by an indexed, unique key (e.g. `created_at, id`) and pass the
last row's cursor: `WHERE (created_at, id) < (:cursor_ts, :cursor_id) ORDER BY … LIMIT
:n`. It's O(page size) regardless of depth and stable under inserts.

**Q9. How do you evolve the schema safely in production?**
A: Today it's hand-run idempotent SQL — honest gap. Production-grade is a versioned
migration tool (Alembic) with an ordered history table and reversible migrations, run
in CI/CD before the app boots. For zero-downtime changes I'd use the expand/contract
pattern: add nullable column → backfill → start writing → make non-null/drop old, so
old and new app versions coexist during the rollout.

**Q10. `bigint` vs `uuid` primary keys — you used both. Trade-offs?**
A: `bigint identity` is small (8 bytes), sequential (great index locality and insert
performance), but enumerable — exposing it can leak row counts and invite IDOR, which
I mitigate with authorization checks. `uuid` is 16 bytes, opaque, and generatable
client-side / shard-friendly, but random UUIDv4 hurts index locality. The modern
answer is **UUIDv7** — time-ordered UUIDs that keep opacity while restoring locality.
For consistency I'd standardize on one; I used both only because the tables were built
in different phases.

---

### Follow-ups interviewers love here
- "Show me the query plan." → be ready to reason about `EXPLAIN ANALYZE`, seq scan vs
  index scan, and why the `user_id` index matters.
- "What isolation level are these transactions?" → Postgres default is **Read
  Committed**; know when you'd need **Repeatable Read**/**Serializable** (e.g. the
  read-modify-write in the rate limiter — which I instead made atomic with an upsert;
  see section 06).
- "This unique index — does it help reads too?" → yes, it's a usable index for lookups
  on `(shelf_id, title)`.
