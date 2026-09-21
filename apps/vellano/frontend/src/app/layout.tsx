import type { Metadata } from "next";
import "@carbon/styles/css/styles.css";
import "./globals.css";

import { AppShell } from "@/components/app-shell";
import { AuthProvider } from "@/lib/auth";

export const metadata: Metadata = {
  title: "Vellano",
  description: "Vellano back office — stock, books, and till",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <AppShell>{children}</AppShell>
        </AuthProvider>
      </body>
    </html>
  );
}
