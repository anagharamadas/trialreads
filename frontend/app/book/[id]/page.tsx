"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { RequireAuth } from "@/components/RequireAuth";
import { Header } from "@/components/Header";
import { StatusBadge } from "@/components/StatusBadge";
import { api, type Book } from "@/lib/api";

function BookDetail() {
  const { id } = useParams<{ id: string }>();
  const [book, setBook] = useState<Book | null>(null);
  const [error, setError] = useState<string | null>(null);

  // No GET /library/{id} yet — fetch the list and find it (fine for Phase 1).
  useEffect(() => {
    api
      .listBooks()
      .then((books) => {
        const found = books.find((b) => String(b.id) === String(id));
        if (found) setBook(found);
        else setError("Book not found.");
      })
      .catch((e) => setError(String(e)));
  }, [id]);

  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto max-w-3xl px-6 py-10">
        <Link href="/" className="text-sm text-accent hover:underline">
          ← Back to shelf
        </Link>

        {error && <p className="mt-6 text-accent">{error}</p>}

        {book && (
          <div className="mt-6 flex gap-8">
            <div className="aspect-[2/3] w-40 flex-shrink-0 overflow-hidden rounded-cover bg-cream-300 shadow-cover">
              {book.cover_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={book.cover_url}
                  alt={book.book}
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex h-full items-center p-3 font-serif text-sm text-ink">
                  {book.book}
                </div>
              )}
            </div>

            <div className="flex-1">
              <h1 className="text-3xl text-ink">{book.book}</h1>
              {book.author && (
                <p className="mt-1 text-lg text-ink-soft">{book.author}</p>
              )}
              <div className="mt-4 flex items-center gap-3">
                <StatusBadge status={book.status} />
                {book.year && (
                  <span className="text-sm text-ink-soft">
                    Finished {book.year}
                  </span>
                )}
              </div>

              <p className="mt-8 text-sm text-ink-soft">
                AI actions (summarise, recommend) and editing arrive in the next
                step.
              </p>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <BookDetail />
    </RequireAuth>
  );
}
