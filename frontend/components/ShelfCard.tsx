"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type Shelf } from "@/lib/api";

/** Overview card: shelf name, book count, and up to 4 cover thumbnails.
 *  Fetches the shelf's books lazily for the preview (libraries are small). */
export function ShelfCard({ shelf }: { shelf: Shelf }) {
  const [covers, setCovers] = useState<(string | null)[]>([]);

  useEffect(() => {
    if (shelf.book_count === 0) return;
    api.shelves
      .books(shelf.id)
      .then((books) => setCovers(books.slice(0, 4).map((b) => b.cover_url)))
      .catch(() => {});
  }, [shelf.id, shelf.book_count]);

  return (
    <Link
      href={`/shelves/${shelf.id}`}
      className="group block rounded-lg bg-white/60 p-4 shadow-card transition-transform duration-200 hover:-translate-y-0.5"
    >
      <div className="flex gap-1.5">
        {[0, 1, 2, 3].map((i) => {
          const c = covers[i];
          return (
            <div
              key={i}
              className="aspect-[2/3] flex-1 overflow-hidden rounded bg-cream-300"
            >
              {c ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={c} alt="" className="h-full w-full object-cover" />
              ) : null}
            </div>
          );
        })}
      </div>
      <h3 className="mt-3 line-clamp-1 text-lg text-ink group-hover:underline">
        {shelf.name}
      </h3>
      <p className="text-sm text-ink-soft">
        {shelf.book_count} {shelf.book_count === 1 ? "book" : "books"}
      </p>
    </Link>
  );
}
