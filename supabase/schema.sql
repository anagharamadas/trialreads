-- ════════════════════════════════════════════════════════════════════════
-- TrialReads — Supabase schema + Row Level Security (Milestone 1)
-- Run this in the Supabase dashboard: SQL Editor → New query → paste → Run.
--
-- ⚠️  VERIFY BEFORE TRUSTING: the plan rightly warns that RLS policy syntax
--     drifts between Supabase versions. This file follows the current canonical
--     pattern (auth.uid() = user_id, wrapped in a scalar subquery for the
--     initplan performance optimization). Cross-check against the live guide:
--     https://supabase.com/docs/guides/database/postgres/row-level-security
-- ════════════════════════════════════════════════════════════════════════

-- ── 1. Table ──────────────────────────────────────────────────────────────
create table if not exists public.library (
    id          bigint generated always as identity primary key,
    user_id     uuid not null references auth.users (id) on delete cascade,
    book        text not null,
    author      text,
    status      text not null default 'Yet to Buy'
                check (status in ('Yet to Buy', 'Reading', 'Ready to Start', 'Finished')),
    year        integer check (year is null or (year between 1000 and 2200)),
    cover_url   text,                          -- nullable, populated later (Google Books)
    created_at  timestamptz not null default now()
);

-- Helpful index: every query is scoped by user_id.
create index if not exists library_user_id_idx on public.library (user_id);

-- ── 2. Enable Row Level Security ──────────────────────────────────────────
alter table public.library enable row level security;

-- ── 3. Per-user policies (each user sees/touches ONLY their own rows) ──────
-- SELECT
drop policy if exists "library_select_own" on public.library;
create policy "library_select_own"
    on public.library for select
    to authenticated
    using ( (select auth.uid()) = user_id );

-- INSERT  (with check guards the NEW row's user_id)
drop policy if exists "library_insert_own" on public.library;
create policy "library_insert_own"
    on public.library for insert
    to authenticated
    with check ( (select auth.uid()) = user_id );

-- UPDATE  (using guards the existing row; with check guards the edited row)
drop policy if exists "library_update_own" on public.library;
create policy "library_update_own"
    on public.library for update
    to authenticated
    using ( (select auth.uid()) = user_id )
    with check ( (select auth.uid()) = user_id );

-- DELETE
drop policy if exists "library_delete_own" on public.library;
create policy "library_delete_own"
    on public.library for delete
    to authenticated
    using ( (select auth.uid()) = user_id );

-- ── 4. Per-user self-filtering view (text-to-SQL isolation) ───────────────
-- The /library/query endpoint points the LLM at THIS view, never at `library`.
-- It hides user_id entirely and filters to the current user via auth.uid().
-- security_invoker = on  →  the underlying table is read AS the querying role,
-- so RLS on `library` is ALSO enforced (defense in depth), not bypassed by the
-- view owner. Requires Postgres 15+ (Supabase is).
create or replace view public.my_library
    with (security_invoker = on) as
    select id, book, author, status, year
    from public.library
    where user_id = (select auth.uid());

grant select on public.my_library to authenticated;

-- ── 5. Per-user daily AI usage counter (rate limiting, Milestone 6) ───────
-- The backend (service role) increments this before each AI call and returns
-- 429 when a user exceeds the daily cap. Durable across Render cold starts.
create table if not exists public.ai_usage (
    user_id uuid not null references auth.users (id) on delete cascade,
    day     date not null default current_date,
    count   integer not null default 0,
    primary key (user_id, day)
);
alter table public.ai_usage enable row level security;
-- No policies: only the backend service role (which bypasses RLS) touches this.

-- ════════════════════════════════════════════════════════════════════════
-- ISOLATION MODEL (Milestone 2, highest-risk step):
--   /library/query runs the LLM-generated SQL on a connection that does
--   SET ROLE authenticated + stamps request.jwt.claims.sub = <user_id>, and
--   only exposes `my_library`. So three things must ALL hold for a leak:
--     (1) the view's WHERE user_id = auth.uid() filter,
--     (2) RLS on the base table (enforced via security_invoker),
--     (3) the engine only being given `my_library`.
--   CRUD endpoints don't use the LLM: user_id comes from the verified JWT and
--   every query is explicitly scoped WHERE user_id = :me.
-- ════════════════════════════════════════════════════════════════════════
