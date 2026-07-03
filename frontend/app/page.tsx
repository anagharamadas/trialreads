"use client";

import { useEffect, useState } from "react";
import { RequireAuth } from "@/components/RequireAuth";
import { Header } from "@/components/Header";
import { BookCover } from "@/components/BookCover";
import { Modal } from "@/components/Modal";
import { BookForm } from "@/components/BookForm";
import { api, type Book } from "@/lib/api";

function Shelf() {
  const [books, setBooks] = useState<Book[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  function load() {
    api
      .listBooks()
      .then(setBooks)
      .catch((e) => setError(String(e)));
  }

  useEffect(load, []);

  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto max-w-6xl px-6 py-10">
        <div className="mb-8 flex items-baseline justify-between">
          <div className="flex items-baseline gap-3">
            <h1 className="text-3xl text-ink">Your Library</h1>
            {books && (
              <span className="text-sm text-ink-soft">
                {books.length} {books.length === 1 ? "book" : "books"}
              </span>
            )}
          </div>
          <button
            onClick={() => setAdding(true)}
            className="rounded-md bg-accent px-4 py-2 text-sm text-white hover:bg-accent-hover"
          >
            + Add book
          </button>
        </div>

        {error && <p className="text-accent">Error: {error}</p>}

        {!books && !error && <p className="text-ink-soft">Loading your shelf…</p>}

        {books && books.length === 0 && (
          <div className="rounded-lg bg-white/60 p-10 text-center shadow-card">
            <p className="text-ink-soft">
              Your shelf is empty. Add your first book to get started.
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

      {adding && (
        <Modal onClose={() => setAdding(false)}>
          <BookForm
            title="Add a book"
            submitLabel="Add book"
            onCancel={() => setAdding(false)}
            onSubmit={async (data) => {
              await api.addBook(data);
              setAdding(false);
              load();
            }}
          />
        </Modal>
      )}
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
