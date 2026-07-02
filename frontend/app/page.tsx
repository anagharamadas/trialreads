"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { RequireAuth } from "@/components/RequireAuth";
import { api } from "@/lib/api";

function Home() {
  const { session, signOut } = useAuth();
  const router = useRouter();
  const [count, setCount] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Stage 1 smoke test: prove the JWT reaches the backend and returns our books.
  useEffect(() => {
    api
      .listBooks()
      .then((books) => setCount(books.length))
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <h1 className="text-4xl text-ink">TrialReads</h1>
      <p className="mt-2 text-ink-soft">
        Signed in as <span className="font-medium">{session?.user.email}</span>
      </p>

      <div className="mt-8 rounded-lg bg-white/60 p-6 shadow-card">
        <h2 className="text-xl">Backend connection</h2>
        {error ? (
          <p className="mt-2 text-accent">Error: {error}</p>
        ) : count === null ? (
          <p className="mt-2 text-ink-soft">Checking…</p>
        ) : (
          <p className="mt-2 text-ink">
            ✅ Your library has <strong>{count}</strong> books. (Shelf UI arrives in
            Stage 2.)
          </p>
        )}
      </div>

      <button
        onClick={async () => {
          await signOut();
          router.replace("/login");
        }}
        className="mt-8 rounded-md bg-accent px-4 py-2 text-white hover:bg-accent-hover"
      >
        Sign out
      </button>
    </main>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <Home />
    </RequireAuth>
  );
}
