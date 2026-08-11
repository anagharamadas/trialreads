# 03 — REST API Design

## 1. The concept

A REST API models a system as **resources** (nouns) addressed by URLs, manipulated with
a small set of HTTP **verbs**, communicating **state** via representations (usually
JSON). Good API design is judged on:

- **Resource modeling & URL structure** — nouns not verbs, hierarchy for containment
  (`/shelves/{id}/books`), plural collections.
- **Correct verb & status-code semantics** — GET (safe/idempotent read), POST (create),
  PUT (idempotent replace/update), DELETE; 200/201/204 for success, 400/401/403/404/409
  for the right failure, 429 for rate limits, 5xx for server faults.
- **Idempotency & safety** — GET/PUT/DELETE should be idempotent; POST usually isn't.
- **Input validation & error contracts** — reject bad input early with a consistent,
  machine-readable error shape.
- **Versioning, pagination, filtering** — how the API evolves and handles large
  collections without breaking clients.
- **Statelessness & auth** — every request carries its own credentials; no server
  session.

## 2. In TrialReads

The API is **FastAPI**, which gives typed request/response models (Pydantic), automatic
validation, and generated OpenAPI docs at `/docs`.

**Resource modeling.** Clean noun hierarchy:
```
GET/POST            /library                 GET/POST/PUT/DELETE  /shelves[/{id}]
PUT/DELETE          /library/{id}            GET/POST             /shelves/{id}/books
POST               /library/query            POST                 /shelves/{id}/books/bulk
POST               /summarise                PUT/DELETE           /shelves/{id}/books/{id}
POST               /recommend                POST                 /shelves/{id}/curate
GET                /covers                    GET                  /health
```
Containment is expressed by nesting (`/shelves/{id}/books`), and RPC-ish actions that
don't map to a noun (`/summarise`, `/library/query`, `/curate`) are modeled as POST
sub-actions — a pragmatic, widely-accepted REST compromise.

**Status codes are deliberate** (`routers/`):
- `201 Created` on POST that creates a row (`add_book`, `create_shelf`, bulk).
- `204 No Content` on DELETE (`delete_book`, `delete_shelf` — no body).
- `404` for both "doesn't exist" and "not yours" — so the API never reveals another
  user's resources (`update_book:94-97`, `_assert_shelf_owner`).
- `409 Conflict` when adding a book already on the shelf (`add_shelf_book:180-183`) —
  the *right* code for a uniqueness violation, not a generic 400.
- `429 Too Many Requests` when the daily AI cap is hit (`rate_limit.py:42-49`).
- `400` for a semantically empty update ("no fields to update").
- `401` for missing/invalid token, with `WWW-Authenticate: Bearer`.

**Validation & error contracts.** Every body is a **Pydantic model** (`schemas.py`), so
FastAPI validates types, required fields, enums (`status` is a `Literal` of the four
legal values), and bounds (`year` `ge=1000, le=2200`) *before* the handler runs, and
returns a consistent `422` with a field-level error list automatically. UUID path params
are parsed to real `uuid` objects; a malformed one returns **404, not a 500**
(`shelves.py:_valid_uuid`).

**Idempotency.** `PUT /library/{id}` and `PUT /shelves/{id}` are idempotent (same body →
same end state). `DELETE` is idempotent-ish: a second delete returns 404 rather than
re-deleting. The **bulk add** is *effectively idempotent by design* — `ON CONFLICT DO
NOTHING` means re-sending the same list adds nothing new, so a client retry after a
network blip is safe.

**Dependency injection.** Cross-cutting concerns (auth, rate limiting) are FastAPI
`Depends(...)`: `get_current_user_id` and `rate_limited_user` are injected into
handlers, so authentication and quota enforcement are declarative and reused, not
copy-pasted. Ordering matters and is used deliberately — `/curate` checks ownership
*before* `enforce_daily_limit`, so probing another user's shelf 404s without burning
quota (`shelves.py:266-269`).

**Auth on every mutating route.** `user_id` comes from the verified JWT, never the body
(section 05).

## 3. Gaps & upgrades to industry standard

- **No pagination.** Collections return everything. Add `limit` + keyset cursor
  (section 02, Q8).
- **No API versioning.** No `/v1` prefix or version header. Fine pre-launch; needed the
  moment external clients depend on the contract. Adding `/v1` now is cheap insurance.
- **No idempotency keys for POST.** The non-bulk creates aren't safe to blind-retry
  (a retry after a lost 201 response creates a duplicate library book — there's no
  uniqueness constraint there like shelves have). Industry pattern: accept an
  `Idempotency-Key` header and dedupe.
- **Error body isn't a standard envelope.** FastAPI returns `{"detail": ...}`; a mature
  API often uses RFC 9457 (Problem Details) with a `type`, `code`, and `trace_id` for
  client-side handling and support.
- **No rate-limit headers.** A 429 doesn't return `Retry-After` / `X-RateLimit-*`, so
  clients can't back off intelligently.
- **No filtering/sorting query params** on `/library` (filtering is client-side today).
- **Content negotiation / HATEStodoAS** — not needed at this scale; worth *knowing* it
  exists.

## 4. Ten interview questions & answers (framed around TrialReads)

**Q1. Why 404 (not 403) when a user hits another user's shelf?**
A: 403 confirms the resource exists but is forbidden, which leaks existence and enables
id enumeration. 404 is indistinguishable from a genuine miss, so the caller learns
nothing. Every ownership check returns 404 for both "gone" and "not yours."

**Q2. Which of your endpoints are idempotent and why does it matter?**
A: GET (all), PUT (`/library/{id}`, `/shelves/{id}` — same body, same end state), and
DELETE (repeat → 404, no extra effect). It matters for safe client retries: on a network
timeout a client can re-send an idempotent request without side effects. POST creates
generally aren't idempotent — which is why the *bulk* add uses `ON CONFLICT DO NOTHING`
to make retries safe.

**Q3. A user adds a book already on the shelf. What status do you return and why not
400?**
A: `409 Conflict`. 400 means "malformed request" — but this request is well-formed; it
just conflicts with current state (a uniqueness violation). 409 tells the client
specifically "duplicate," which they can handle differently from a validation error.

**Q4. How do you validate input, and what happens on bad input?**
A: Every body is a Pydantic model, so FastAPI validates types, required fields, enums,
and numeric bounds before my handler runs, returning a 422 with a field-level error
list automatically. Path UUIDs are parsed explicitly — a bad UUID returns 404, not an
unhandled 500. So handlers only ever see valid, typed data.

**Q5. Walk me through the dependency injection for auth and rate limiting.**
A: `get_current_user_id` is a dependency that verifies the JWT and returns the user id;
`rate_limited_user` depends on it and additionally enforces the daily cap. Handlers just
declare `user_id: str = Depends(rate_limited_user)`. It's declarative, reused, and
testable. Crucially I control ordering: `/curate` runs the ownership check *before* the
rate-limit increment, so a probe of someone else's shelf 404s without consuming quota
or running paid inference.

**Q6. How would you add pagination to `GET /shelves/{id}/books`?**
A: Keyset pagination on `(reading_order, id)` with a `limit` and an opaque `cursor` of
the last row; `WHERE (reading_order, id) > (:c1, :c2) ORDER BY reading_order, id LIMIT
:n`. O(page size) at any depth and stable under inserts, unlike OFFSET. I'd return a
`next_cursor` in the response.

**Q7. How do you version this API without breaking the frontend?**
A: Prefix routes with `/v1` and treat the contract as frozen once external clients
depend on it. Breaking changes go to `/v2`; additive changes (new optional fields) stay
in `/v1`. Because it's a monorepo, the frontend types are generated from the same models,
so I can also run contract tests. Today there's no version prefix — an honest gap I'd
close before opening the API to third parties.

**Q8. Your POST creates aren't idempotent — is that a problem?**
A: For `POST /library` yes: if the 201 response is lost and the client retries, it
creates a duplicate book (no uniqueness constraint there, unlike shelves). The fix is an
`Idempotency-Key` header — the client sends a UUID, the server dedupes on it for a
window. Stripe's API is the canonical example. Bulk add is already retry-safe via
`ON CONFLICT`.

**Q9. `/summarise` and `/library/query` aren't really "resources." Is that RESTful?**
A: They're RPC-style actions modeled as POST sub-actions, which is a pragmatic and
widely-accepted REST compromise for operations that don't map to CRUD on a noun. Purists
might model a `summaries` resource you POST to; in practice a verb-y POST endpoint is
clearer here. I keep them POST (not GET) because they're expensive, non-cacheable, and
have a request body.

**Q10. What makes your API observable and debuggable?**
A: FastAPI auto-generates OpenAPI docs at `/docs`. Every request produces an
OpenTelemetry server span labeled by route template, method, and status (section 09),
structured JSON logs carry the trace id, and Sentry captures exceptions. So for any
request I can find its trace, its logs, and — for LLM calls — the Langfuse run.

---

### Follow-ups interviewers love here
- "Why POST for `/library/query` instead of GET with a query param?" → it has a body,
  it's expensive/non-idempotent, and query strings have length/encoding limits.
- "What's the difference between PUT and PATCH?" → PUT replaces (idempotent), PATCH
  partially updates; my `PUT /library/{id}` is actually PATCH-semantics (partial), a
  common pragmatic naming choice worth acknowledging.
- "How do clients discover the contract?" → generated OpenAPI/Swagger at `/docs`.
