# QA Checklist — Phase 2 (Shelves + Curation Agent)

Manual verification for the new surface area. Automated equivalents of most rows
were run during development (see commit messages); this is the human pass, run
against **production** (Vercel + Render) before considering Phase 2 launched.

Create two throwaway accounts, **A** and **B**, for the isolation rows.

## 1. Two-account isolation matrix (shelves / shelf_books)

For every row: perform the action as **B** against **A's** resource. Expected =
404 / not-visible, never A's data.

| Endpoint / action | As B against A's shelf | Expect |
|---|---|---|
| `GET /shelves` | — | B sees only B's shelves |
| `GET /shelves/{A_shelf}/books` | list A's books | 404 |
| `PUT /shelves/{A_shelf}` | rename | 404 |
| `DELETE /shelves/{A_shelf}` | delete | 404 |
| `POST /shelves/{A_shelf}/books` | add book | 404 |
| `POST /shelves/{A_shelf}/books/bulk` | bulk add | 404 |
| `PUT /shelves/{A_shelf}/books/{id}` | edit | 404 |
| `DELETE /shelves/{A_shelf}/books/{id}` | remove | 404 |
| `POST /shelves/{A_shelf}/curate` | run agent | **404 before any inference** (no quota burned) |
| Direct DB (Supabase SQL editor, impersonate B) | `select * from shelf_books` | only B's rows (RLS) |
| Adversarial: A inserts `shelf_books` row with `shelf_id` = B's | — | RLS violation (blocked) |

## 2. Text-to-SQL cross-table check

The `/library/query` engine is scoped to the `my_library` view, but runs on an
RLS-scoped connection. Confirm it cannot leak the new tables cross-user:

- As **B**, `POST /library/query` with `"SELECT * FROM shelf_books"` and
  `"list every shelf book"` → answer must **not** contain any of **A's** shelf
  titles. (RLS is the sandbox; it covers the new tables.)
- Confirm `auth.users` and other users' rows are unreachable (blocked / empty).
- Sanity: normal library questions ("how many have I finished?") still work.

## 3. Curation agent — happy path

- Empty shelf → "Build this shelf with AI" opens the chat panel.
- Vague goal ("I want to learn X") → agent asks 2–4 clarifying questions, **no
  proposal yet**.
- Answer them → agent returns a proposal card: overview + 5–10 books in reading
  order, each with cover, author, reason.
- **Spot-check 2–3 titles against Google Books** — every proposed book must be
  real (the hallucination test).
- Untick a book → "Add N to shelf" updates → Accept → panel closes, shelf grid
  populated in order, `added_by = agent`.
- Reorder (up/down), Remove, and "Add to library" work on agent-added books.

## 4. Curation agent — failure modes (should degrade, never invent)

| Input | Expected behaviour |
|---|---|
| One-word / vague goal ("business") | asks clarifying questions, no invented list |
| "Give me 50 books" | caps at ≤10; states the limit |
| "…and include magazines/journals" | books only; periodicals filtered out |
| Obscure topic with few books | proposes fewer (3–4) and says so honestly |
| User refuses to answer clarifying Qs | proceeds with a best-effort, still-grounded list or asks once more; never fabricates |

Every proposed book, in all cases, must be Google-Books-validated (grounded).

## 5. Rate limiting & spend

- `/curate` counts toward the per-user daily AI cap (shared with summarise /
  recommend / library-query). Hitting the cap → 429 on all four.
- After a few real curation sessions, check the backend token logs
  (`curate: tokens=…`) and sanity-check the monthly projection against the
  OpenAI spend limit.

## 6. Monitoring

- Sentry (backend + frontend) is global, so the new routes/endpoints report
  errors automatically. Trigger one error (e.g. stop Supabase briefly or hit a
  bad path) and confirm it appears in Sentry.

## 7. Production smoke test (deployed stack)

1. Open the Vercel URL, sign in.
2. Library: filters work (Status / Author / Year, combined, clear).
3. Shelves: create a shelf → Build with AI → clarify → accept → shelf populated.
4. Add-to-library on an agent book → appears in Library.
5. Reorder / remove / delete shelf.
6. Sign out, sign back in → data persisted.
7. Re-run the two-account isolation spot-check (§1) against production.
