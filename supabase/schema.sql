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

-- ════════════════════════════════════════════════════════════════════════
-- NOTE: the backend will connect with the SERVICE-ROLE key, which BYPASSES
-- RLS. That means RLS alone does NOT protect the multi-user text-to-SQL
-- feature — the backend must itself force a WHERE user_id = <current_user>
-- filter (Milestone 2, the highest-risk step). RLS is the safety net for any
-- path that uses the anon/authenticated role (e.g. the frontend's direct
-- Supabase client calls), not a substitute for backend-side scoping.
-- ════════════════════════════════════════════════════════════════════════
