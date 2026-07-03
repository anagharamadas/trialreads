"use client";

import { useState } from "react";
import type { Book } from "@/lib/api";

const STATUSES: Book["status"][] = [
  "Yet to Buy",
  "Reading",
  "Ready to Start",
  "Finished",
];

export type BookFormData = {
  book: string;
  author: string;
  status: Book["status"];
  year: number | null;
};

const inputCls =
  "w-full rounded-md border border-cream-300 bg-white px-3 py-2 outline-none focus:border-accent";

export function BookForm({
  initial,
  title,
  submitLabel,
  onSubmit,
  onCancel,
}: {
  initial?: Partial<Book>;
  title: string;
  submitLabel: string;
  onSubmit: (data: BookFormData) => Promise<void>;
  onCancel: () => void;
}) {
  const [book, setBook] = useState(initial?.book ?? "");
  const [author, setAuthor] = useState(initial?.author ?? "");
  const [status, setStatus] = useState<Book["status"]>(
    initial?.status ?? "Yet to Buy"
  );
  const [year, setYear] = useState(initial?.year ? String(initial.year) : "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!book.trim()) {
      setError("Title is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onSubmit({
        book: book.trim(),
        author: author.trim(),
        status,
        year: year ? parseInt(year, 10) : null,
      });
    } catch (err) {
      setError(String(err));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <h2 className="text-xl text-ink">{title}</h2>

      <div>
        <label className="mb-1 block text-sm text-ink-soft">Title *</label>
        <input
          className={inputCls}
          value={book}
          onChange={(e) => setBook(e.target.value)}
          placeholder="Book title"
          autoFocus
        />
      </div>

      <div>
        <label className="mb-1 block text-sm text-ink-soft">Author</label>
        <input
          className={inputCls}
          value={author}
          onChange={(e) => setAuthor(e.target.value)}
          placeholder="Author (optional)"
        />
      </div>

      <div className="flex gap-4">
        <div className="flex-1">
          <label className="mb-1 block text-sm text-ink-soft">Status</label>
          <select
            className={inputCls}
            value={status}
            onChange={(e) => setStatus(e.target.value as Book["status"])}
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="w-28">
          <label className="mb-1 block text-sm text-ink-soft">Year</label>
          <input
            className={inputCls}
            type="number"
            min={1000}
            max={2200}
            value={year}
            onChange={(e) => setYear(e.target.value)}
            placeholder="—"
          />
        </div>
      </div>

      {error && <p className="text-sm text-accent">{error}</p>}

      <div className="flex justify-end gap-3 pt-2">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border border-cream-300 px-4 py-2 text-ink hover:bg-cream-200"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={busy}
          className="rounded-md bg-accent px-4 py-2 text-white hover:bg-accent-hover disabled:opacity-60"
        >
          {busy ? "Saving…" : submitLabel}
        </button>
      </div>
    </form>
  );
}
