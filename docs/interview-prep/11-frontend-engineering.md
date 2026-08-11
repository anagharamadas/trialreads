# 11 — Frontend Engineering (Next.js & React)

## 1. The concept

Frontend engineering at interview depth is about **component architecture**, **state
management**, **rendering strategy**, and **performance/UX**. Core ideas:

- **Declarative UI & components** — UI is a function of state; you compose small,
  reusable components. Reuse via extraction, not duplication.
- **State: local vs. lifted vs. global** — keep state as local as possible; lift when
  siblings must share; use context/store for truly cross-cutting state (auth, theme).
- **The React model** — re-render on state change, `key`s for list reconciliation, effects
  for side-effects, controlled inputs, avoiding unnecessary renders.
- **Rendering strategies** — CSR, SSR, SSG, ISR, and (Next App Router) **Server vs. Client
  Components**: server components render on the server with no JS shipped; client components
  (`"use client"`) run in the browser and hold interactivity/state.
- **Data fetching & async UX** — loading/empty/error states, optimistic updates,
  request/response typing.
- **Performance** — bundle size, code-splitting, image optimization, Core Web Vitals
  (LCP/CLS/INP).
- **Accessibility & correctness** — semantic HTML, labels, keyboard support.

## 2. In TrialReads

**Next.js 14 App Router** (`frontend/app/`) with file-system routing, including a dynamic
route `shelves/[id]` and an OAuth `auth/callback`. Most interactive pages are **Client
Components** (`"use client"`) because they hold auth/session state and fetch per-user data.

**Component architecture & reuse.** Small, composable components (`components/`). The key
reuse decision: the cover grid was **extracted into a shared `CoverGrid`** used by both the
Library and shelf-detail pages, so the two look identical and the layout lives in one place —
"extract, don't duplicate." `RatingStars`, `StatusBadge`, `Modal`, `BookCover`, and
`ShelfBookCard` are similarly single-responsibility.

**State management, chosen per scope:**
- **Global (cross-cutting): React Context.** `AuthProvider` holds the Supabase session and
  exposes it via `useAuth()`; `RequireAuth` consumes it to implement **protected routes**
  (redirect to `/login` if unauthenticated). Auth is genuinely app-wide, so context is the
  right tool — no Redux needed at this size.
- **Local component state: `useState`.** The curation chat (`CurationChat`) keeps the message
  history, the pending proposal, the per-book `selected` set, and busy/error flags all as
  local state — because that state matters only to that panel. It sends the full history to
  the backend each turn (keeping the backend stateless — section 01).
- **Derived state, not stored.** The Library filter (`FilterBar` + `applyFilters`) computes
  the visible list from `books` and the active filters on each render, and derives the
  dropdown options (distinct authors/years) from the loaded data. Nothing filtered is stored
  — it's derived, which avoids the classic "two sources of truth" bug.

**Async UX done properly.** Data-fetching components render explicit **loading / empty /
error** states (e.g., the shelf list: "Loading shelves…", a styled empty state, and an error
line), not a blank screen. The chat shows a "Thinking…" indicator during the multi-second
agent turn and an **error state with a Retry button** tuned for Render cold starts.

**A typed API boundary.** `lib/api.ts` is a single typed client: it attaches the Supabase JWT
to every request, centralizes error handling, and exports TypeScript types (`Book`,
`ShelfBook`, `CurateProposal`, …) shared across components — so a backend contract change
surfaces as a type error, not a runtime surprise.

**Accept-flow UX.** The proposal card renders the agent's list with per-book checkboxes
(default checked), and "Add N to shelf" renumbers `reading_order` over the *selected* subset
before the bulk call — a small but correct detail (the order the user accepts is the order
stored).

**Performance/monitoring.** `@vercel/speed-insights` reports **Core Web Vitals** from real
users; Sentry (`@sentry/nextjs`) captures client errors; Next handles code-splitting per
route automatically; covers use plain `<img>` with graceful fallback + an `onError` → text
placeholder (the "book covers render as anime" incident turned out to be a *browser
extension*, verified by loading the same data in a clean browser — a good "debug the
environment, not just the code" story).

## 3. Gaps & upgrades to industry standard

- **Mostly client-rendered; not leveraging Server Components / SSR.** Pages fetch per-user
  data client-side after auth, so there's a loading flash and no server-rendered first paint
  for authed content. A more advanced setup uses Server Components + server-side Supabase
  auth (cookies) to render the shelf on the server. Trade-off: simpler client-only auth vs.
  faster first paint + SEO.
- **No data-fetching/caching library.** Fetching is hand-rolled `useEffect` + `useState`.
  **TanStack Query** (or SWR) would add caching, dedup, background refetch, and optimistic
  updates for free, and remove a lot of boilerplate.
- **No optimistic updates.** Reorder/add/remove wait for the server round-trip before the UI
  updates. Optimistic UI (update immediately, roll back on error) would feel instant.
- **N+1 on the shelves overview.** Each `ShelfCard` fetches its own books for the cover
  preview — N requests for N shelves. A backend field returning preview covers, or a single
  batched call, fixes it (mirrors the backend N+1 discussion, section 02).
- **No component tests.** No React Testing Library / Playwright. UX has been verified
  manually/by browser automation, not in CI.
- **Accessibility not audited.** Some controls (reorder arrows) have `aria-label`s, but
  there's no systematic a11y pass (focus management in modals, keyboard traps, contrast).
- **No error boundaries** beyond Sentry capture; a thrown render error could blank a route.

## 4. Ten interview questions & answers (framed around TrialReads)

**Q1. Server vs. Client Components — which did you use and why?**
A: Mostly Client Components, because the interactive pages hold auth/session state and fetch
per-user data in the browser with the user's JWT. Server Components render on the server with
no JS shipped and are great for static/SEO content — the honest upgrade here is to move the
authed shelf render server-side (with cookie-based Supabase auth) for a faster first paint
and no loading flash.

**Q2. How do you manage state, and why no Redux?**
A: By scope. Auth is app-wide, so it's React Context (`AuthProvider` + `useAuth`). Panel-
specific state (chat history, the pending proposal, selected books) is local `useState`.
Filtered lists are *derived* from state on render, not stored. At this size that's all I
need; Redux/Zustand earns its place when many distant components mutate shared state — I
don't have that.

**Q3. Your Library filter — is the filtered list stored in state?**
A: No, it's derived. I store the raw `books` and the active filters, and compute the visible
list (and the dropdown options) on each render. Storing the filtered result would create two
sources of truth that drift when the underlying data changes. Derive, don't duplicate.

**Q4. How do protected routes work?**
A: A `RequireAuth` wrapper reads the session from the auth context; while loading it shows a
spinner, and if there's no session it redirects to `/login`. Every authed page renders inside
it. The real security is still the backend (JWT verification + RLS) — the client guard is
UX, not a security boundary.

**Q5. Walk me through the async UX of the curation chat.**
A: Local state holds the message array, a busy flag, an error, and the current proposal. On
send I append the user message, POST the full history, show a "Thinking…" indicator (agent
turns take 10–60s), then render the assistant reply and, if present, a proposal card with
checkboxes. Errors show a Retry button (Render cold starts can time out). A newer proposal
supersedes the previous card. History lives here on the client, which keeps the backend
stateless.

**Q6. What would optimistic updates change here?**
A: Reorder/add/remove currently wait for the server before updating the UI, so there's a
lag. Optimistic UI updates local state immediately, fires the request, and rolls back if it
fails — the reorder would feel instant. TanStack Query makes this a first-class pattern with
automatic rollback on error.

**Q7. There's an N+1 on your shelves page. Where and how do you fix it?**
A: Each `ShelfCard` fetches its shelf's books just to show up to four cover thumbnails — N
requests for N shelves. Fix: have the backend `GET /shelves` return a few preview cover URLs
per shelf (one query with a lateral/aggregate), or batch the previews into one call. Same N+1
lesson as the backend, on the client side.

**Q8. How do you keep the frontend and backend types in sync?**
A: A single typed API client (`lib/api.ts`) exports TypeScript types mirroring the backend's
Pydantic models, and every component imports them. So a contract change surfaces as a compile
error. The stronger version is generating types from the backend's OpenAPI schema so they
can't drift at all.

**Q9. How do you monitor real-user frontend performance?**
A: `@vercel/speed-insights` reports Core Web Vitals (LCP, CLS, INP) from real users, and
Sentry captures client-side errors with stack traces. Next.js code-splits per route
automatically to keep initial JS small. The gap is trace-linking a browser action to the
backend request — propagating a trace header would give end-to-end traces.

**Q10. Tell me about a tricky frontend bug you debugged.**
A: Users reported every book cover rendering as an anime image. The data and code were fine —
I proved it by loading the exact same library (same `cover_url`s) in a clean browser, where
covers rendered correctly, and by fetching the image URLs server-side (real book covers). It
was a browser *extension* rewriting `<img>` sources. The lesson: when the code looks right,
suspect the environment — reproduce in a clean context before changing code.

---

### Follow-ups interviewers love here
- "Why does React need `key`s?" → stable identity for list reconciliation; index keys break
  on reorder — relevant since shelves reorder.
- "CSR vs SSR vs SSG trade-offs?" → CSR simple but slow first paint/no SEO; SSR fresh +
  SEO but server cost; SSG fastest but static.
- "How would you make the shelf reorder feel instant?" → optimistic update + rollback.
