"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { RequireAuth } from "@/components/RequireAuth";
import { Header } from "@/components/Header";
import { CoverGrid } from "@/components/CoverGrid";
import { ShelfBookCard } from "@/components/ShelfBookCard";
import { Modal } from "@/components/Modal";
import { CurationChat } from "@/components/CurationChat";
import { api, type Shelf, type ShelfBook } from "@/lib/api";

function ShelfDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [shelf, setShelf] = useState<Shelf | null>(null);
  const [books, setBooks] = useState<ShelfBook[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [curating, setCurating] = useState(false);

  const load = useCallback(() => {
    api.shelves
      .list()
      .then((all) => {
        const found = all.find((s) => s.id === id);
        if (found) setShelf(found);
        else setError("Shelf not found.");
      })
      .catch((e) => setError(String(e)));
    api.shelves
      .books(id)
      .then(setBooks)
      .catch((e) => setError(String(e)));
  }, [id]);

  useEffect(load, [load]);

  // Swap reading_order with the adjacent book (orders are kept distinct on add).
  async function move(i: number, dir: -1 | 1) {
    if (!books) return;
    const j = i + dir;
    if (j < 0 || j >= books.length) return;
    const a = books[i];
    const b = books[j];
    const oa = a.reading_order ?? i + 1;
    const ob = b.reading_order ?? j + 1;
    await api.shelves.updateBook(id, a.id, { reading_order: ob });
    await api.shelves.updateBook(id, b.id, { reading_order: oa });
    load();
  }

  async function removeBook(bookId: string) {
    await api.shelves.removeBook(id, bookId);
    load();
  }

  async function addToLibrary(book: ShelfBook) {
    const created = await api.addBook({
      book: book.title,
      author: book.author ?? "",
      status: "Yet to Buy",
    });
    await api.shelves.updateBook(id, book.id, { library_book_id: created.id });
    load();
  }

  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto max-w-6xl px-6 py-10">
        <Link href="/shelves" className="text-sm text-accent hover:underline">
          ← All shelves
        </Link>

        {error && <p className="mt-6 text-accent">{error}</p>}

        {shelf && (
          <div className="mt-4 mb-8 flex items-start justify-between gap-4">
            <div>
              <h1 className="text-3xl text-ink">{shelf.name}</h1>
              {shelf.description && (
                <p className="mt-1 text-ink-soft">{shelf.description}</p>
              )}
              <p className="mt-1 text-sm text-ink-soft">
                {books ? books.length : shelf.book_count}{" "}
                {(books ? books.length : shelf.book_count) === 1 ? "book" : "books"}
              </p>
            </div>
            <div className="flex flex-shrink-0 gap-2">
              <button
                onClick={() => setCurating(true)}
                className="rounded-md bg-accent px-4 py-2 text-sm text-white hover:bg-accent-hover"
              >
                ✨ Build with AI
              </button>
              <button
                onClick={() => setAdding(true)}
                className="rounded-md border border-cream-300 px-4 py-2 text-sm text-ink hover:bg-cream-200"
              >
                + Add book
              </button>
              <button
                onClick={() => setDeleting(true)}
                className="rounded-md border border-accent/40 px-4 py-2 text-sm text-accent hover:bg-accent/5"
              >
                Delete shelf
              </button>
            </div>
          </div>
        )}

        {books && books.length === 0 && (
          <div className="rounded-lg bg-white/60 p-10 text-center shadow-card">
            <p className="text-ink-soft">This shelf is empty.</p>
            <button
              onClick={() => setCurating(true)}
              className="mt-4 rounded-md bg-accent px-4 py-2 text-sm text-white hover:bg-accent-hover"
            >
              ✨ Build this shelf with AI
            </button>
          </div>
        )}

        {books && books.length > 0 && (
          <CoverGrid>
            {books.map((b, i) => (
              <ShelfBookCard
                key={b.id}
                book={b}
                index={i}
                total={books.length}
                onMove={(dir) => move(i, dir)}
                onRemove={() => removeBook(b.id)}
                onAddToLibrary={() => addToLibrary(b)}
              />
            ))}
          </CoverGrid>
        )}
      </main>

      {curating && (
        <CurationChat
          shelfId={id}
          onClose={() => setCurating(false)}
          onAccepted={load}
        />
      )}

      {adding && (
        <AddBookModal
          shelfId={id}
          nextOrder={(books?.length ?? 0) + 1}
          onClose={() => setAdding(false)}
          onAdded={() => {
            setAdding(false);
            load();
          }}
        />
      )}

      {deleting && shelf && (
        <Modal onClose={() => setDeleting(false)}>
          <div className="space-y-4">
            <h2 className="text-xl text-ink">Delete this shelf?</h2>
            <p className="text-ink-soft">
              &ldquo;{shelf.name}&rdquo; and all its books will be removed. Books
              in your library are not affected.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setDeleting(false)}
                className="rounded-md border border-cream-300 px-4 py-2 text-ink hover:bg-cream-200"
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  await api.shelves.remove(id);
                  router.push("/shelves");
                }}
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

function AddBookModal({
  shelfId,
  nextOrder,
  onClose,
  onAdded,
}: {
  shelfId: string;
  nextOrder: number;
  onClose: () => void;
  onAdded: () => void;
}) {
  const [title, setTitle] = useState("");
  const [author, setAuthor] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setBusy(true);
    setError(null);
    try {
      // fetch cover + Google Books rating in one call (both best-effort)
      let cover_url: string | null = null;
      let average_rating: number | null = null;
      let ratings_count: number | null = null;
      let info_link: string | null = null;
      try {
        const gb = await api.getCover(title.trim(), author.trim());
        cover_url = gb.cover_url;
        average_rating = gb.average_rating;
        ratings_count = gb.ratings_count;
        info_link = gb.info_link;
      } catch {
        /* metadata is best-effort */
      }
      await api.shelves.addBook(shelfId, {
        title: title.trim(),
        author: author.trim() || null,
        cover_url,
        reading_order: nextOrder,
        average_rating,
        ratings_count,
        info_link,
      });
      onAdded();
    } catch (err) {
      setError(String(err));
      setBusy(false);
    }
  }

  return (
    <Modal onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <h2 className="text-xl text-ink">Add a book to this shelf</h2>
        <input
          autoFocus
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Title"
          className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 outline-none focus:border-accent"
        />
        <input
          value={author}
          onChange={(e) => setAuthor(e.target.value)}
          placeholder="Author (optional)"
          className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 outline-none focus:border-accent"
        />
        {error && <p className="text-sm text-accent">{error}</p>}
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-cream-300 px-4 py-2 text-ink hover:bg-cream-200"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={busy || !title.trim()}
            className="rounded-md bg-accent px-4 py-2 text-white hover:bg-accent-hover disabled:opacity-60"
          >
            {busy ? "Adding…" : "Add book"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <ShelfDetail />
    </RequireAuth>
  );
}
