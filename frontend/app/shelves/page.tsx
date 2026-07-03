"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { RequireAuth } from "@/components/RequireAuth";
import { Header } from "@/components/Header";
import { ShelfCard } from "@/components/ShelfCard";
import { Modal } from "@/components/Modal";
import { api, type Shelf } from "@/lib/api";

function ShelvesOverview() {
  const router = useRouter();
  const [shelves, setShelves] = useState<Shelf[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);

  function load() {
    api.shelves
      .list()
      .then(setShelves)
      .catch((e) => setError(String(e)));
  }
  useEffect(load, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    try {
      const shelf = await api.shelves.create({
        name: name.trim(),
        description: description.trim() || null,
      });
      router.push(`/shelves/${shelf.id}`);
    } catch (err) {
      setError(String(err));
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto max-w-6xl px-6 py-10">
        <div className="mb-8 flex items-baseline justify-between">
          <div className="flex items-baseline gap-3">
            <h1 className="text-3xl text-ink">Shelves</h1>
            {shelves && (
              <span className="text-sm text-ink-soft">
                {shelves.length} {shelves.length === 1 ? "shelf" : "shelves"}
              </span>
            )}
          </div>
          <button
            onClick={() => setCreating(true)}
            className="rounded-md bg-accent px-4 py-2 text-sm text-white hover:bg-accent-hover"
          >
            + New Shelf
          </button>
        </div>

        {error && <p className="text-accent">Error: {error}</p>}
        {!shelves && !error && <p className="text-ink-soft">Loading shelves…</p>}

        {shelves && shelves.length === 0 && (
          <div className="rounded-lg bg-white/60 p-10 text-center shadow-card">
            <p className="text-ink-soft">
              No shelves yet. Create one to group books into a reading list.
            </p>
          </div>
        )}

        {shelves && shelves.length > 0 && (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {shelves.map((s) => (
              <ShelfCard key={s.id} shelf={s} />
            ))}
          </div>
        )}
      </main>

      {creating && (
        <Modal onClose={() => setCreating(false)}>
          <form onSubmit={create} className="space-y-4">
            <h2 className="text-xl text-ink">New shelf</h2>
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Shelf name"
              className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 outline-none focus:border-accent"
            />
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Description (optional)"
              rows={3}
              className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 outline-none focus:border-accent"
            />
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setCreating(false)}
                className="rounded-md border border-cream-300 px-4 py-2 text-ink hover:bg-cream-200"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={busy || !name.trim()}
                className="rounded-md bg-accent px-4 py-2 text-white hover:bg-accent-hover disabled:opacity-60"
              >
                {busy ? "Creating…" : "Create shelf"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <ShelvesOverview />
    </RequireAuth>
  );
}
