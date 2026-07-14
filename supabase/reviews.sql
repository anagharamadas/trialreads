-- ════════════════════════════════════════════════════════════════════════
-- TrialReads — Google Books ratings on shelf books
-- Run in the Supabase SQL Editor (or via a trusted postgres connection).
-- Idempotent: safe to re-run.
--
-- Ratings are captured at add/grounding time from the same Google Books
-- response that already validates the book (zero extra API quota), then
-- displayed on shelf cards and curation proposals. The Google Books API only
-- exposes AGGREGATE ratings (averageRating 1-5 + ratingsCount) plus a link to
-- the book's Google Books page — written reviews live behind info_link.
-- Values are point-in-time snapshots, not live; NULL = Google had no rating.
-- ════════════════════════════════════════════════════════════════════════

alter table public.shelf_books
    add column if not exists average_rating numeric(2,1)
        check (average_rating is null or (average_rating between 0 and 5)),
    add column if not exists ratings_count integer
        check (ratings_count is null or ratings_count >= 0),
    add column if not exists info_link text;
