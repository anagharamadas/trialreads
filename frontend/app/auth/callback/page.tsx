"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";

/**
 * Landing page for the email-confirmation link (signUp's emailRedirectTo).
 *
 * The client uses the implicit flow with detectSessionInUrl:true, so on a
 * successful confirmation Supabase redirects here with the session tokens in the
 * URL hash and the client establishes the session as it initialises. We just
 * wait for that session, then continue into the app. If the link was invalid or
 * expired, Supabase instead puts the reason in the hash (#error=...), which we
 * surface rather than spinning forever.
 */
export default function AuthCallbackPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const hash = new URLSearchParams(window.location.hash.slice(1));
    if (hash.get("error")) {
      setError(
        hash.get("error_description")?.replace(/\+/g, " ") ||
          "This confirmation link is invalid or has expired.",
      );
      return;
    }

    // The session may be established slightly after mount (detectSessionInUrl
    // runs during client init), so both listen for the change and check once.
    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session) router.replace("/");
    });
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) router.replace("/");
    });
    return () => sub.subscription.unsubscribe();
  }, [router]);

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-sm text-center">
        <h1 className="text-4xl text-ink">TrialReads</h1>
        {error ? (
          <>
            <p className="mt-4 text-sm text-accent">{error}</p>
            <p className="mt-6 text-sm text-ink-soft">
              Request a new link from the{" "}
              <Link href="/signup" className="text-accent hover:underline">
                sign-up page
              </Link>
              , or{" "}
              <Link href="/login" className="text-accent hover:underline">
                sign in
              </Link>{" "}
              if you already confirmed.
            </p>
          </>
        ) : (
          <p className="mt-4 text-ink-soft">Confirming your account…</p>
        )}
      </div>
    </main>
  );
}
