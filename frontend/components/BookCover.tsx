"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, type Book } from "@/lib/api";
import { StatusBadge } from "./StatusBadge";

/**
 * A single book on the shelf. Shows the stored cover_url if present; otherwise
 * looks one up from Google Books (via the backend) once, persists it, and falls
 * back to a typographic "spine" placeholder when none is found.
 */
export function BookCover({ book }: { book: Book }) {
  const [cover, setCover] = useState<string | null>(book.cover_url);
  const [failed, setFailed] = useState(false);
  const tried = useRef(false);

  useEffect(() => {
    if (cover || tried.current) return;
    tried.current = true;
    api
      .getCover(book.book, book.author ?? "")
      .then((r) => {
        if (r.cover_url) {
          setCover(r.cover_url);
          // Persist so we don't re-query Google next time.
          api.updateBook(book.id, { cover_url: r.cover_url }).catch(() => {});
        }
      })
      .catch(() => {});
  }, [book, cover]);

  return (
    <Link href={`/book/${book.id}`} className="group block">
      <div className="relative aspect-[2/3] w-full overflow-hidden rounded-cover bg-cream-300 shadow-cover transition-transform duration-200 group-hover:-translate-y-1">
        {cover && !failed ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={cover}
            alt={book.book}
            className="h-full w-full object-cover"
            onError={() => setFailed(true)}
          />
        ) : (
          <div className="flex h-full flex-col justify-between bg-gradient-to-br from-cream-200 to-cream-300 p-3">
            <span className="line-clamp-5 font-serif text-sm leading-snug text-ink">
              {book.book}
            </span>
            <span className="line-clamp-1 text-xs text-ink-soft">
              {book.author}
            </span>
          </div>
        )}
        <div className="absolute right-1.5 top-1.5">
          <StatusBadge status={book.status} />
        </div>
      </div>
      <p className="mt-2 line-clamp-1 text-sm text-ink group-hover:underline">
        {book.book}
      </p>
      {book.author && (
        <p className="line-clamp-1 text-xs text-ink-soft">{book.author}</p>
      )}
    </Link>
  );
}
