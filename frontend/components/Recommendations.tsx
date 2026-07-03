"use client";

import { useState } from "react";
import { api, type Recommendation } from "@/lib/api";

export function Recommendations({
  bookName,
  authorName,
}: {
  bookName: string;
  authorName?: string;
}) {
  const [recs, setRecs] = useState<Recommendation[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.recommend(bookName, authorName ?? "");
      setRecs(res.recommendations);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-10">
      {!recs && (
        <button
          onClick={load}
          disabled={busy}
          className="rounded-md bg-accent px-4 py-2 text-white hover:bg-accent-hover disabled:opacity-60"
        >
          {busy ? "Finding similar books…" : "Get recommendations"}
        </button>
      )}

      {error && <p className="mt-3 text-sm text-accent">{error}</p>}

      {recs && (
        <div className="space-y-4">
          <h2 className="text-xl text-ink">You might also like</h2>
          {recs.map((r, i) => (
            <div
              key={i}
              className="rounded-lg bg-white/60 p-4 shadow-card"
            >
              <p className="text-ink">
                <span className="font-medium">{r.title}</span>
                {r.author && (
                  <span className="text-ink-soft"> by {r.author}</span>
                )}
              </p>
              {r.reason && (
                <p className="mt-1 text-sm italic text-ink-soft">{r.reason}</p>
              )}
              {r.amazon_link && (
                <a
                  href={r.amazon_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-3 inline-block rounded-md border border-accent/40 px-3 py-1.5 text-sm text-accent hover:bg-accent/5"
                >
                  🛒 Buy on Amazon
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
