import type { Metadata } from "next";
import Link from "next/link";
import "./style.css";

export const metadata: Metadata = {
  title: "Furniture Storefront Preview",
  description: "A private preview of the new furniture storefront.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en-ZA">
      <body>
        <header className="site-header">
          <Link href="/" className="wordmark">THE COLLECTOR</Link>
          <span>Private catalogue preview</span>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
