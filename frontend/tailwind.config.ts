import type { Config } from "tailwindcss";

// Apple Books–inspired warm palette. Values are tuned by eye, not Apple's actual
// tokens. Adjust cream/ink to taste.
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        cream: {
          DEFAULT: "#FAF7F2", // page background
          50: "#FDFCFA",
          100: "#FAF7F2",
          200: "#F1EBE1",
          300: "#E6DCCB",
        },
        ink: {
          DEFAULT: "#2B2622", // primary text
          soft: "#6B6157",    // secondary text
        },
        accent: {
          DEFAULT: "#B5522E", // warm terracotta for actions
          hover: "#9C4526",
        },
      },
      fontFamily: {
        serif: ["Georgia", "Cambria", "Times New Roman", "serif"],
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
      boxShadow: {
        // soft shelf shadow under each cover
        cover: "0 6px 16px rgba(43, 38, 34, 0.18), 0 2px 4px rgba(43, 38, 34, 0.10)",
        card: "0 2px 10px rgba(43, 38, 34, 0.08)",
      },
      borderRadius: {
        cover: "6px",
      },
    },
  },
  plugins: [],
};

export default config;
