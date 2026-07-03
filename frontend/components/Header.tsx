"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "./AuthProvider";

export function Header() {
  const { session, signOut } = useAuth();
  const router = useRouter();

  return (
    <header className="sticky top-0 z-10 border-b border-cream-300 bg-cream/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="text-2xl font-serif text-ink">
          TrialReads
        </Link>
        <div className="flex items-center gap-4 text-sm">
          <span className="hidden text-ink-soft sm:inline">
            {session?.user.email}
          </span>
          <button
            onClick={async () => {
              await signOut();
              router.replace("/login");
            }}
            className="rounded-md border border-cream-300 px-3 py-1.5 text-ink hover:bg-cream-200"
          >
            Sign out
          </button>
        </div>
      </div>
    </header>
  );
}
