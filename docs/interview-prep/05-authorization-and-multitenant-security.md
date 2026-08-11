# 05 — Authorization & Multi-Tenant Security (Row-Level Security)

> This is TrialReads' strongest senior-level signal. The text-to-SQL feature is a
> textbook "how do you stop an LLM from leaking other users' data" problem, and the
> answer here is a real defense-in-depth design.

## 1. The concept

**Authentication** ("who are you") is separate from **authorization** ("what may you
touch"). This section is authorization in a **multi-tenant** system: one shared
database holds many users' (tenants') data, and the hard requirement is **tenant
isolation** — user A must *never* read or write user B's rows, through any code path.

The engineering ideas interviewers probe:

- **Where to enforce authorization.** In application code (every query filtered by the
  caller's id), in the database (Row-Level Security), or both. Both is "defense in
  depth" — a second control that holds even if the first has a bug.
- **Least privilege.** Each component runs with the minimum access it needs. A backend
  that connects as an all-powerful admin role and forgets a `WHERE user_id =` is one
  bug away from a full breach.
- **The confused-deputy / IDOR problem.** If authorization is derived from
  attacker-controlled input (a body field, a path id) instead of the authenticated
  identity, the attacker can act as someone else.
- **Untrusted code generating queries.** An LLM writing SQL is *untrusted input turned
  into code*. You cannot rely on prompt instructions ("only query your own rows") for
  security — you need a control the model cannot talk its way past.

## 2. In TrialReads

There are **two authorization paths**, each isolated by a different mechanism, because
they have different threat models.

### Path A — CRUD endpoints: code-level scoping (identity from the token)

The pooled engine (`db.py`) connects as Supabase's **service role**, which *bypasses*
RLS. So for ordinary CRUD, the real guard is application code:

- `user_id` **always comes from the verified JWT**, never the request body
  (`get_current_user_id` → the `user_id` dependency). This closes the IDOR/confused-
  deputy hole: you cannot pass someone else's id.
- Every statement is explicitly scoped `WHERE user_id = :me` and, for nested resources,
  ownership is checked first. `_assert_shelf_owner` runs before any shelf-book operation
  and returns **404 (not 403)** if the shelf isn't yours — so we don't even reveal that
  another user's shelf exists (`routers/shelves.py:57-63`).
- **A subtle authorization bug the RLS policy specifically closes:** a naive "insert is
  fine if `user_id = auth.uid()`" check would let attacker A insert a `shelf_books` row
  with `user_id = A` but `shelf_id =` *B's* shelf — planting rows on someone else's
  shelf. The `shelf_books` INSERT/UPDATE policy therefore *also* requires
  `EXISTS (select 1 from shelves where id = shelf_id and user_id = auth.uid())`
  (`shelves.sql:91-100`). The API's `_assert_shelf_owner` enforces the same rule in
  code — defense in depth.

### Path B — text-to-SQL: Row-Level Security is the enforcement

This is the interesting one. `/library/query` turns a user's natural language into SQL
via an LLM and executes it. Prompt instructions are **not** a security boundary, so the
isolation is enforced three ways at once (`services/library_query.py`, `schema.sql`):

1. **A self-filtering view.** The LLM is pointed only at the `my_library` view, which
   `select id, book, author, status, year from library where user_id = (select
   auth.uid())` and *doesn't even expose `user_id`* (`schema.sql:67-73`). The model
   can't filter on a column it can't see.
2. **An RLS-scoped connection.** Queries run on a **non-pooled** engine whose every
   connection is stamped, on connect, with `SET ROLE authenticated` and
   `request.jwt.claims.sub = <user_id>` (`library_query.py:92-105`). So the connection
   runs as the *authenticated* role — which RLS governs — impersonating this user. Even
   a raw `SELECT * FROM library` returns only this user's rows, because the base-table
   RLS policy applies.
3. **`security_invoker = on` on the view.** So the view reads the base table *as the
   querying role*, meaning base-table RLS is enforced *through* the view rather than
   bypassed by the view owner (`schema.sql:67-68`).

For a leak, the view's `WHERE`, the base-table RLS, **and** the table scoping would all
have to fail simultaneously. And **`NullPool` + `engine.dispose()` per request** means
no connection (and no lingering `SET ROLE` / claims) is ever reused across users —
critical, because a pooled connection carrying one user's claims to the next request
*would* be a leak.

### Least privilege in the roles

- The **service role** (RLS-bypassing) is used only for trusted, code-scoped CRUD and
  the `ai_usage` counter — never for LLM-generated SQL.
- The **authenticated role** (RLS-governed) is used for the untrusted text-to-SQL path.
  It also can't reach system tables — a probe of `auth.users` from that connection
  returns *permission denied*, verified during hardening.

### This was tested adversarially, not assumed

Two-account tests (documented in `QA-phase2.md`): user B gets 404 on every one of A's
shelf endpoints; B's text-to-SQL asking for `shelf_books` / other users' data returns
nothing; planting a row on another user's shelf raises an RLS violation. Isolation is
*verified by trying to break it*, which is exactly the framing to bring to an interview.

## 3. Gaps & upgrades to industry standard

- **Two enforcement models to keep in sync.** CRUD relies on code scoping (service role
  bypasses RLS); only text-to-SQL relies on RLS. A stricter design would run *all*
  queries through the RLS-scoped authenticated role so the database is the single source
  of truth and a forgotten `WHERE` can't leak. The trade-off is per-request role setup
  cost and losing the connection pool for those paths.
- **A new table without RLS is a silent hole.** Isolation depends on every
  user-scoped table having RLS enabled + policies. There's no automated check that a
  future table can't ship without them. Industry practice: a CI test that asserts RLS
  is enabled on every table in a user-data schema.
- **No column-/field-level authorization or roles.** It's binary owner-or-not. Real
  systems often need shared resources, org/team scoping, roles (viewer/editor), and
  audit logs of access.
- **Per-request `create_engine` in text-to-SQL** is correct for isolation but not free;
  a pool of pre-warmed authenticated connections keyed by nothing (claims set per
  checkout, reset on checkin) would cut latency — carefully, since a reset bug reintroduces
  the leak.
- **Secrets/keys** are environment variables on Render/Vercel. Fine for this scale;
  a larger org uses a secrets manager (Vault, AWS Secrets Manager) with rotation and
  audit.

## 4. Ten interview questions & answers (framed around TrialReads)

**Q1. Your backend connects as a role that bypasses RLS. Isn't that dangerous — why not
just rely on RLS everywhere?**
A: It's a deliberate split by threat model. For CRUD, the queries are *fixed* and I
control them, so I scope every one `WHERE user_id = :me` with the id taken from the
verified JWT — simple and fast on a pooled connection. For the text-to-SQL path, the
SQL is *LLM-generated and untrusted*, so I can't trust my own code to scope it — there
I switch to the RLS-governed `authenticated` role so Postgres enforces isolation
physically. Using RLS everywhere is cleaner and I'd consider it, but it costs per-request
role setup and the connection pool; I chose RLS where the risk actually is.

**Q2. How do you stop the text-to-SQL LLM from reading another user's books?**
A: Three layers, none of which is a prompt instruction. The model only sees a
`my_library` view that filters to `auth.uid()` and hides `user_id`. Queries execute on
a connection running as the `authenticated` role with the user's JWT claims stamped, so
base-table RLS applies — even `SELECT * FROM library` returns only their rows. And the
view uses `security_invoker`, so RLS is enforced through it. All three must fail to leak.
I verified it by asking, as user B, to dump `shelf_books` and other users' data — it
returns nothing.

**Q3. Why is a leaked/pooled connection a security risk in the text-to-SQL path?**
A: I set the role and JWT claims *on the connection*. If that connection went back to a
pool and served the next request without a reset, request two would run with request
one's identity — a cross-user leak. That's why the scoped engine uses `NullPool` and
`dispose()`s per request: connections are never reused, so claims never bleed across
users.

**Q4. You return 404 instead of 403 when B accesses A's shelf. Why?**
A: A 403 ("forbidden") confirms the resource exists but you can't have it — that leaks
existence and lets an attacker enumerate valid ids. 404 ("not found") is
indistinguishable from a real miss, so B learns nothing about A's shelves. It's the
same reasoning as not revealing whether an email is registered on a login form.

**Q5. Walk me through an IDOR attempt against your API and why it fails.**
A: IDOR = insecure direct object reference: the attacker swaps an id to touch someone
else's object. Say B calls `PUT /shelves/{A_shelf_id}`. The endpoint never trusts a body
`user_id`; it derives the caller from the JWT and runs `UPDATE … WHERE id = :sid AND
user_id = :me`. Since `:me` is B, the WHERE matches zero rows → 404. Even if I'd
forgotten that clause, RLS on the base table (were we on the authenticated role) is the
backstop.

**Q6. There's a specific insert attack your `shelf_books` policy blocks that a simple
`user_id` check wouldn't. What is it?**
A: Planting rows on another user's shelf. A naive policy "allow insert if new row's
`user_id = auth.uid()`" passes when A inserts with `user_id = A` but `shelf_id =` B's
shelf — A's own row, on B's shelf. So the INSERT policy also requires an `EXISTS` check
that the target `shelf_id` belongs to `auth.uid()`. The API enforces the same via
`_assert_shelf_owner` — defense in depth.

**Q7. What does "defense in depth" mean concretely here — give me the layers.**
A: Independent controls so one bug isn't a breach. Layer 1: the JWT is verified and
`user_id` comes only from it. Layer 2: application code scopes every query and checks
ownership (404 on miss). Layer 3: Postgres RLS on every user table. Layer 4 (text-to-SQL):
the self-filtering view + `security_invoker`. Layer 5: least privilege — untrusted SQL
never runs as the RLS-bypassing service role, and can't reach system tables.

**Q8. How would you make sure a *future* table can't ship without isolation?**
A: Make it impossible to forget. A CI test that queries `pg_tables`/`pg_policies` and
fails the build if any table in the user-data schema has RLS disabled or lacks
select/insert/update/delete policies. Plus a code review checklist and a template. Today
that's manual — an honest gap.

**Q9. The pooled backend engine bypasses RLS. If an attacker got SQL injection into a
CRUD endpoint, what happens, and how do you prevent injection?**
A: On the service role, injection would bypass RLS — so I never build SQL from user
strings. All queries use SQLAlchemy **bound parameters** (`:me`, `:sid`), so user input
is data, never concatenated into SQL. UUID path params are parsed to real `uuid` objects
before binding (bad ones → 404, not a 500). The one place untrusted text *becomes* SQL —
the LLM path — is deliberately on the RLS-governed role, not the service role.

**Q10. If you rebuilt this for 10M users and stricter compliance, what changes?**
A: Run all reads/writes through the RLS `authenticated` role (single source of truth),
add org/team scoping and roles beyond owner-or-not, add an access audit log, move
secrets to a managed vault with rotation, add the CI "RLS-on-every-table" guard, and
consider tenant sharding (RLS is row-level isolation, not resource isolation — a noisy
tenant still shares the DB). I'd also add per-tenant rate limits and data-export/delete
tooling for GDPR-style requests.

---

### Follow-ups interviewers love here
- "RLS vs. application-level filtering — when would you *not* use RLS?" → high-throughput
  services where per-request role setup cost matters, or non-Postgres stores; then the
  DB can't be your isolation layer and code scoping + tests must be airtight.
- "How do you test isolation?" → adversarial two-account tests in CI (create A and B,
  assert every cross-access is denied), not just happy-path tests.
- "Is `auth.uid()` trustworthy inside the DB?" → yes *because* the backend sets
  `request.jwt.claims` on a connection it controls; the value originates from a
  cryptographically verified JWT (section 04), not from the client directly.
