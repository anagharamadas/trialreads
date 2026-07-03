import Link from "next/link";

export const metadata = { title: "Privacy Policy — TrialReads" };

export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <Link href="/login" className="text-sm text-accent hover:underline">
        ← Back
      </Link>
      <h1 className="mt-4 text-4xl text-ink">Privacy Policy</h1>
      <p className="mt-2 text-sm text-ink-soft">Last updated: 2026-07-03</p>

      <div className="mt-8 space-y-6 text-ink">
        <section>
          <h2 className="text-xl">What this app is</h2>
          <p className="mt-2 text-ink-soft">
            TrialReads is a personal reading app. You create an account, keep a
            list of your books, and use AI features to summarise books, get
            recommendations, and ask questions about your library.
          </p>
        </section>

        <section>
          <h2 className="text-xl">What we collect</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-ink-soft">
            <li>
              <strong>Account:</strong> your email address and an encrypted
              password (handled by our auth provider; we never see your password
              in plain text).
            </li>
            <li>
              <strong>Your library:</strong> the books you add — title, author,
              status, year, and cover image reference.
            </li>
            <li>
              <strong>AI requests:</strong> the book titles and questions you
              submit to the summarise, recommend, and library-question features.
            </li>
            <li>
              <strong>Basic usage counts</strong> for rate limiting (how many AI
              requests you make per day).
            </li>
          </ul>
        </section>

        <section>
          <h2 className="text-xl">How your data is used</h2>
          <p className="mt-2 text-ink-soft">
            Your library is private to your account and protected by row-level
            security — no other user can access it. We use your data only to
            provide the app&rsquo;s features. We do not sell your data or use it
            for advertising.
          </p>
        </section>

        <section>
          <h2 className="text-xl">Third-party services</h2>
          <p className="mt-2 text-ink-soft">
            To provide the app we share the minimum necessary data with:
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-ink-soft">
            <li>
              <strong>Supabase</strong> — database and authentication (stores
              your account and library).
            </li>
            <li>
              <strong>OpenAI</strong> — processes the book titles and questions
              you submit to generate summaries, recommendations, and answers.
            </li>
            <li>
              <strong>Google Books</strong> — looked up by title/author to fetch
              cover images.
            </li>
            <li>
              <strong>Render / Vercel</strong> — host the backend and frontend.
            </li>
          </ul>
          <p className="mt-2 text-ink-soft">
            Recommendation links point to Amazon search results; we have no
            affiliate or data-sharing relationship with Amazon.
          </p>
        </section>

        <section>
          <h2 className="text-xl">Data retention &amp; your rights</h2>
          <p className="mt-2 text-ink-soft">
            Your data is kept until you delete it or request account deletion.
            You can edit or delete any book at any time from within the app. To
            delete your account and all associated data, contact us at the email
            below.
          </p>
        </section>

        <section>
          <h2 className="text-xl">Contact</h2>
          <p className="mt-2 text-ink-soft">
            Questions or requests: <strong>anaghamulloth@gmail.com</strong>.
          </p>
        </section>

        <p className="border-t border-cream-300 pt-6 text-xs text-ink-soft">
          This policy is provided as a starting point and is not legal advice.
          If you collect data from users in the EU/UK or other regulated regions,
          review it against GDPR/local requirements before public launch.
        </p>
      </div>
    </main>
  );
}
