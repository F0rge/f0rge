import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "oklch(var(--background) / <alpha-value>)",
        foreground: "oklch(var(--foreground) / <alpha-value>)",
        card: { DEFAULT: "oklch(var(--card) / <alpha-value>)", foreground: "oklch(var(--card-foreground) / <alpha-value>)" },
        popover: { DEFAULT: "oklch(var(--popover) / <alpha-value>)", foreground: "oklch(var(--popover-foreground) / <alpha-value>)" },
        primary: { DEFAULT: "oklch(var(--primary) / <alpha-value>)", foreground: "oklch(var(--primary-foreground) / <alpha-value>)" },
        secondary: { DEFAULT: "oklch(var(--secondary) / <alpha-value>)", foreground: "oklch(var(--secondary-foreground) / <alpha-value>)" },
        muted: { DEFAULT: "oklch(var(--muted) / <alpha-value>)", foreground: "oklch(var(--muted-foreground) / <alpha-value>)" },
        accent: { DEFAULT: "oklch(var(--accent) / <alpha-value>)", foreground: "oklch(var(--accent-foreground) / <alpha-value>)" },
        destructive: { DEFAULT: "oklch(var(--destructive) / <alpha-value>)", foreground: "oklch(var(--destructive-foreground) / <alpha-value>)" },
        border: "oklch(var(--border) / <alpha-value>)",
        input: "oklch(var(--input) / <alpha-value>)",
        ring: "oklch(var(--ring) / <alpha-value>)",
      },
      borderRadius: {
        sm: "calc(var(--radius) - 4px)",
        md: "calc(var(--radius) - 2px)",
        lg: "var(--radius)",
        xl: "calc(var(--radius) + 4px)",
      },
      fontFamily: { sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"] },
    },
  },
  plugins: [],
};
export default config;
