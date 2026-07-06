import type { Metadata } from "next";
import { SpeedInsights } from "@vercel/speed-insights/next";
import "./globals.css";
import { AuthProvider } from "@/components/AuthProvider";

export const metadata: Metadata = {
  title: "TrialReads",
  description: "Your personal reading shelf — summaries, library, and recommendations.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>{children}</AuthProvider>
        {/* Core Web Vitals RUM — no-op in dev; only reports on Vercel prod deploys */}
        <SpeedInsights />
      </body>
    </html>
  );
}
