/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    // Google Books cover thumbnails (Stage 2)
    remotePatterns: [
      { protocol: "https", hostname: "books.google.com" },
      { protocol: "http", hostname: "books.google.com" },
      { protocol: "https", hostname: "*.googleusercontent.com" },
    ],
  },
};

export default nextConfig;
