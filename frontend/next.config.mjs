import { withSentryConfig } from "@sentry/nextjs";

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Required in Next 14 for instrumentation.ts (Sentry server/edge init) to run.
  experimental: {
    instrumentationHook: true,
  },
  images: {
    // Google Books cover thumbnails
    remotePatterns: [
      { protocol: "https", hostname: "books.google.com" },
      { protocol: "http", hostname: "books.google.com" },
      { protocol: "https", hostname: "*.googleusercontent.com" },
    ],
  },
};

// Wrap with Sentry. No auth token here → source maps are not uploaded at build
// time (fine for Phase 1); runtime error capture still works when the DSN is set.
export default withSentryConfig(nextConfig, {
  silent: true,
  telemetry: false,
  sourcemaps: { disable: true },
  disableLogger: true,
});
