"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    // emailRedirectTo pins the confirmation link back to THIS origin's
    // /auth/callback (localhost in dev, the Vercel domain in prod) instead of
    // falling back to the project's Site URL — which is what made the link land
    // on an unreachable address. The URL must be in Supabase's Redirect URLs
    // allow-list or Supabase ignores it and reverts to the Site URL.
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
    });
    setBusy(false);
    if (error) {
      setError(error.message);
      return;
    }
    // If email confirmation is OFF, a session is returned and we can go straight in.
    if (data.session) router.replace("/");
    else setNotice("Check your email to confirm your account, then sign in.");
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <h1 className="text-center text-4xl text-ink">TrialReads</h1>
        <p className="mt-2 text-center text-ink-soft">Create your shelf.</p>

        <form onSubmit={onSubmit} className="mt-8 space-y-4">
          <input
            type="email"
            required
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-md border border-cream-300 bg-white px-4 py-2 outline-none focus:border-accent"
          />
          <input
            type="password"
            required
            minLength={6}
            placeholder="Password (min 6 chars)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-md border border-cream-300 bg-white px-4 py-2 outline-none focus:border-accent"
          />
          {error && <p className="text-sm text-accent">{error}</p>}
          {notice && <p className="text-sm text-ink-soft">{notice}</p>}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-md bg-accent px-4 py-2 text-white hover:bg-accent-hover disabled:opacity-60"
          >
            {busy ? "Creating…" : "Sign up"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-ink-soft">
          Already have an account?{" "}
          <Link href="/login" className="text-accent hover:underline">
            Sign in
          </Link>
        </p>
        <p className="mt-8 text-center text-xs text-ink-soft">
          By signing up you agree to our{" "}
          <Link href="/privacy" className="hover:underline">
            Privacy Policy
          </Link>
          .
        </p>
      </div>
    </main>
  );
}
