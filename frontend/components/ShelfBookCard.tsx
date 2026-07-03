"use client";

import { useState } from "react";
import { api, type ShelfBook } from "@/lib/api";

/** A book on a shelf detail page: cover/placeholder with an order badge,
 *  the agent's reason on hover, up/down reorder, remove, and (when not yet in
 *  the library) an Add-to-library action. */
export function ShelfBookCard({
  book,
  index,
  total,
  onMove,
  onRemove,
  onAddToLibrary,
}: {
  book: ShelfBook;
  index: number;
  total: number;
  onMove: (dir: -1 | 1) => void;
  onRemove: () => void;
  onAddToLibrary: () => Promise<void>;
}) {
  const [busy, setBusy] = useState<null | "up" | "down" | "remove" | "add">(null);

  async function run(kind: "up" | "down" | "remove" | "add", fn: () => Promise<void> | void) {
    setBusy(kind);
    try {
      await fn();
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="group">
      <div className="relative aspect-[2/3] w-full overflow-hidden rounded-cover bg-cream-300 shadow-cover">
        {book.cover_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={book.cover_url}
            alt={book.title}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full flex-col justify-between bg-gradient-to-br from-cream-200 to-cream-300 p-3">
            <span className="line-clamp-5 font-serif text-sm leading-snug text-ink">
              {book.title}
            </span>
            <span className="line-clamp-1 text-xs text-ink-soft">
              {book.author}
            </span>
          </div>
        )}

        {/* reading-order badge */}
        {book.reading_order != null && (
          <div className="absolute left-1.5 top-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-ink/80 text-xs font-medium text-white">
            {book.reading_order}
          </div>
        )}

        {/* reason overlay on hover/tap */}
        {book.reason && (
          <div className="pointer-events-none absolute inset-0 flex items-end bg-ink/0 p-2 opacity-0 transition-opacity duration-200 group-hover:bg-ink/60 group-hover:opacity-100">
            <p className="line-clamp-4 text-xs leading-snug text-white">
              {book.reason}
            </p>
          </div>
        )}
      </div>

      <p className="mt-2 line-clamp-1 text-sm text-ink">{book.title}</p>
      {book.author && (
        <p className="line-clamp-1 text-xs text-ink-soft">{book.author}</p>
      )}

      <div className="mt-1.5 flex items-center gap-1 text-xs">
        <button
          onClick={() => run("up", () => onMove(-1))}
          disabled={index === 0 || busy !== null}
          className="rounded border border-cream-300 px-1.5 py-0.5 text-ink-soft hover:bg-cream-200 disabled:opacity-40"
          aria-label="Move up"
        >
          ↑
        </button>
        <button
          onClick={() => run("down", () => onMove(1))}
          disabled={index === total - 1 || busy !== null}
          className="rounded border border-cream-300 px-1.5 py-0.5 text-ink-soft hover:bg-cream-200 disabled:opacity-40"
          aria-label="Move down"
        >
          ↓
        </button>
        <button
          onClick={() => run("remove", onRemove)}
          disabled={busy !== null}
          className="rounded border border-cream-300 px-1.5 py-0.5 text-ink-soft hover:bg-accent/5 hover:text-accent disabled:opacity-40"
        >
          Remove
        </button>
      </div>

      {book.library_book_id == null && (
        <button
          onClick={() => run("add", onAddToLibrary)}
          disabled={busy !== null}
          className="mt-1.5 w-full rounded border border-accent/40 px-2 py-1 text-xs text-accent hover:bg-accent/5 disabled:opacity-40"
        >
          {busy === "add" ? "Adding…" : "+ Add to library"}
        </button>
      )}
      {book.library_book_id != null && (
        <p className="mt-1.5 text-xs text-emerald-700">✓ In your library</p>
      )}
    </div>
  );
}
