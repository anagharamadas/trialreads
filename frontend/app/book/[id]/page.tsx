"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { RequireAuth } from "@/components/RequireAuth";
import { Header } from "@/components/Header";
import { StatusBadge } from "@/components/StatusBadge";
import { Modal } from "@/components/Modal";
import { BookForm } from "@/components/BookForm";
import { Recommendations } from "@/components/Recommendations";
import { api, type Book } from "@/lib/api";

function BookDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [book, setBook] = useState<Book | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);

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

  async function handleDelete() {
    if (!book) return;
    setDeleting(true);
    try {
      await api.deleteBook(book.id);
      router.push("/");
    } catch (e) {
      setError(String(e));
      setDeleting(false);
    }
  }

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
                  <span className="text-sm text-ink-soft">Finished {book.year}</span>
                )}
              </div>

              <div className="mt-8 flex gap-3">
                <button
                  onClick={() => setEditing(true)}
                  className="rounded-md border border-cream-300 px-4 py-2 text-ink hover:bg-cream-200"
                >
                  Edit
                </button>
                <button
                  onClick={() => setDeleting(true)}
                  className="rounded-md border border-accent/40 px-4 py-2 text-accent hover:bg-accent/5"
                >
                  Delete
                </button>
              </div>

            </div>
          </div>
        )}

        {book && (
          <div className="mt-10">
            {/* Summaries moved to shelf books not yet in the library — a
                try-before-you-buy preview makes no sense for owned books. */}
            <Recommendations bookName={book.book} authorName={book.author ?? ""} />
          </div>
        )}
      </main>

      {editing && book && (
        <Modal onClose={() => setEditing(false)}>
          <BookForm
            title="Edit book"
            submitLabel="Save changes"
            initial={book}
            onCancel={() => setEditing(false)}
            onSubmit={async (data) => {
              const updated = await api.updateBook(book.id, data);
              setBook(updated);
              setEditing(false);
            }}
          />
        </Modal>
      )}

      {deleting && book && (
        <Modal onClose={() => setDeleting(false)}>
          <div className="space-y-4">
            <h2 className="text-xl text-ink">Delete this book?</h2>
            <p className="text-ink-soft">
              &ldquo;{book.book}&rdquo; will be removed from your library. This
              can&rsquo;t be undone.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setDeleting(false)}
                className="rounded-md border border-cream-300 px-4 py-2 text-ink hover:bg-cream-200"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                className="rounded-md bg-accent px-4 py-2 text-white hover:bg-accent-hover"
              >
                Delete
              </button>
            </div>
          </div>
        </Modal>
      )}
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
