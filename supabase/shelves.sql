-- ════════════════════════════════════════════════════════════════════════
-- TrialReads Phase 2 — Shelves feature: `shelves` + `shelf_books` (+ RLS)
-- Run in the Supabase SQL Editor (or via a trusted postgres connection).
-- Idempotent: safe to re-run.
--
-- Model: a "shelf" is a tag/collection (Goodreads-style). Shelf items are
-- independent of the library — the curation agent recommends books the user
-- may not own — with an OPTIONAL link back to a library row.
--
-- ⚠️  VERIFY BEFORE TRUSTING (same rule as Phase 1): RLS policy syntax drifts
--     between Supabase versions. This follows the current canonical pattern
--     ((select auth.uid()) = user_id — the scalar-subquery initplan form).
--     Cross-check against the live guide:
--     https://supabase.com/docs/guides/database/postgres/row-level-security
-- ════════════════════════════════════════════════════════════════════════

-- ── 1. shelves ────────────────────────────────────────────────────────────
create table if not exists public.shelves (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users (id) on delete cascade,
    name        text not null,
    description text,
    created_at  timestamptz not null default now()
);

create index if not exists shelves_user_id_idx on public.shelves (user_id);

-- ── 2. shelf_books ────────────────────────────────────────────────────────
-- user_id is deliberately DENORMALIZED here (not just derivable via shelf_id)
-- so the RLS policies below are a simple equality check without a join.
create table if not exists public.shelf_books (
    id               uuid primary key default gen_random_uuid(),
    shelf_id         uuid not null references public.shelves (id) on delete cascade,
    user_id          uuid not null references auth.users (id) on delete cascade,
    -- optional link to an owned library row; keep the shelf entry if the
    -- library row is later deleted
    library_book_id  bigint references public.library (id) on delete set null,
    title            text not null,
    author           text,
    cover_url        text,
    reason           text,               -- the agent's one-line "why this book"
    reading_order    integer,            -- position in the shelf's sequence
    added_by         text not null default 'user'
                     check (added_by in ('user', 'agent')),
    created_at       timestamptz not null default now()
);

-- No duplicate titles on the same shelf. NULLS NOT DISTINCT (Postgres 15+)
-- so two entries with the same title and NULL author also count as duplicates.
create unique index if not exists shelf_books_dedupe_idx
    on public.shelf_books (shelf_id, title, author) nulls not distinct;

create index if not exists shelf_books_user_id_idx on public.shelf_books (user_id);
create index if not exists shelf_books_shelf_order_idx
    on public.shelf_books (shelf_id, reading_order);

-- ── 3. Row Level Security ─────────────────────────────────────────────────
alter table public.shelves enable row level security;
alter table public.shelf_books enable row level security;

-- shelves: each user sees/touches only their own rows.
drop policy if exists "shelves_select_own" on public.shelves;
create policy "shelves_select_own" on public.shelves
    for select to authenticated
    using ( (select auth.uid()) = user_id );

drop policy if exists "shelves_insert_own" on public.shelves;
create policy "shelves_insert_own" on public.shelves
    for insert to authenticated
    with check ( (select auth.uid()) = user_id );

drop policy if exists "shelves_update_own" on public.shelves;
create policy "shelves_update_own" on public.shelves
    for update to authenticated
    using ( (select auth.uid()) = user_id )
    with check ( (select auth.uid()) = user_id );

drop policy if exists "shelves_delete_own" on public.shelves;
create policy "shelves_delete_own" on public.shelves
    for delete to authenticated
    using ( (select auth.uid()) = user_id );

-- shelf_books: same ownership check, PLUS insert/update must point at a shelf
-- the caller owns. A plain user_id check would let user A insert a row with
-- user_id = A but shelf_id = B's shelf — the adversarial case this blocks.
drop policy if exists "shelf_books_select_own" on public.shelf_books;
create policy "shelf_books_select_own" on public.shelf_books
    for select to authenticated
    using ( (select auth.uid()) = user_id );

drop policy if exists "shelf_books_insert_own" on public.shelf_books;
create policy "shelf_books_insert_own" on public.shelf_books
    for insert to authenticated
    with check (
        (select auth.uid()) = user_id
        and exists (
            select 1 from public.shelves s
            where s.id = shelf_id and s.user_id = (select auth.uid())
        )
    );

drop policy if exists "shelf_books_update_own" on public.shelf_books;
create policy "shelf_books_update_own" on public.shelf_books
    for update to authenticated
    using ( (select auth.uid()) = user_id )
    with check (
        (select auth.uid()) = user_id
        and exists (
            select 1 from public.shelves s
            where s.id = shelf_id and s.user_id = (select auth.uid())
        )
    );

drop policy if exists "shelf_books_delete_own" on public.shelf_books;
create policy "shelf_books_delete_own" on public.shelf_books
    for delete to authenticated
    using ( (select auth.uid()) = user_id );

-- ════════════════════════════════════════════════════════════════════════
-- MANUAL ISOLATION TEST (run before building any app code on top of this)
--
-- 1. Authentication → Users: create two test users, note their UUIDs (A, B).
-- 2. As service role (SQL editor default), seed one shelf + one book each:
--      insert into shelves (user_id, name) values ('<A>', 'A shelf'), ('<B>', 'B shelf');
--      insert into shelf_books (shelf_id, user_id, title)
--        select id, user_id, user_id || ' book' from shelves;
-- 3. Impersonate A and verify visibility:
--      set local role authenticated;
--      set local request.jwt.claims = '{"sub":"<A>","role":"authenticated"}';
--      select * from shelves;      -- must return ONLY A's shelf
--      select * from shelf_books;  -- must return ONLY A's book
-- 4. ADVERSARIAL (still as A): try to plant a row on B's shelf:
--      insert into shelf_books (shelf_id, user_id, title)
--        values ('<B_shelf_id>', '<A>', 'planted');
--    → must FAIL with a row-level security violation.
-- 5. Also as A: update/delete B's rows → 0 rows affected; reset with:
--      reset role;
-- ════════════════════════════════════════════════════════════════════════
