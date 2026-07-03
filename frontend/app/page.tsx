"use client";

import { useEffect, useState } from "react";
import { RequireAuth } from "@/components/RequireAuth";
import { Header } from "@/components/Header";
import { BookCover } from "@/components/BookCover";
import { api, type Book } from "@/lib/api";

function Shelf() {
  const [books, setBooks] = useState<Book[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listBooks()
      .then(setBooks)
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto max-w-6xl px-6 py-10">
        <div className="mb-8 flex items-baseline justify-between">
          <h1 className="text-3xl text-ink">Your Library</h1>
          {books && (
            <span className="text-sm text-ink-soft">
              {books.length} {books.length === 1 ? "book" : "books"}
            </span>
          )}
        </div>

        {error && <p className="text-accent">Error: {error}</p>}

        {!books && !error && (
          <p className="text-ink-soft">Loading your shelf…</p>
        )}

        {books && books.length === 0 && (
          <div className="rounded-lg bg-white/60 p-10 text-center shadow-card">
            <p className="text-ink-soft">
              Your shelf is empty. Adding books arrives in the next step.
            </p>
          </div>
        )}

        {books && books.length > 0 && (
          <div className="grid grid-cols-2 gap-x-6 gap-y-8 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
            {books.map((b) => (
              <BookCover key={b.id} book={b} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <Shelf />
    </RequireAuth>
  );
}
