"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button, Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@f0rge/ui";
import { HeaderAuth } from "./header-auth";
import { Wordmark } from "./wordmark";

const links = [
  { href: "/shop", label: "Shop all" },
  { href: "/collections", label: "Collections" },
  { href: "/#our-approach", label: "Our approach" },
];

export function SiteHeader({ clerkConfigured }: { clerkConfigured: boolean }) {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  return <header className="site-header">
    <Link href="/" className="wordmark" aria-label="Vellano home"><Wordmark /></Link>
    <nav className="desktop-navigation" aria-label="Main navigation">
      {links.map((link) => <Link key={link.href} href={link.href} aria-current={pathname === link.href ? "page" : undefined}>{link.label}</Link>)}
    </nav>
    <div className="header-actions">
      <div className="desktop-account"><Link href="/account" aria-current={pathname.startsWith("/account") ? "page" : undefined}>Account</Link>{clerkConfigured && <HeaderAuth />}</div>
      <Link className="header-bag" href="/bag" aria-current={pathname === "/bag" ? "page" : undefined}>
        <svg width="18" height="20" viewBox="0 0 20 22" fill="none" aria-hidden="true"><path d="M3 7h14l1 13H2L3 7Z" stroke="currentColor" strokeWidth="1.25"/><path d="M6 8V5a4 4 0 0 1 8 0v3" stroke="currentColor" strokeWidth="1.25"/></svg>
        Bag
      </Link>
      <Dialog open={menuOpen} onOpenChange={setMenuOpen}>
        <DialogTrigger render={<Button variant="ghost" className="mobile-menu-trigger" aria-label="Open menu" />}>
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M2 6h16M2 14h16" stroke="currentColor" strokeWidth="1.25"/></svg>
        </DialogTrigger>
        <DialogContent className="mobile-menu">
          <DialogTitle className="wordmark"><Wordmark /></DialogTitle>
          <DialogDescription>Find furniture for your everyday life.</DialogDescription>
          <nav aria-label="Mobile navigation">
            {links.map((link) => <Link key={link.href} href={link.href} onClick={() => setMenuOpen(false)} aria-current={pathname === link.href ? "page" : undefined}>{link.label}<span aria-hidden="true">↗</span></Link>)}
            <Link href="/account" onClick={() => setMenuOpen(false)}>Account<span aria-hidden="true">↗</span></Link>
            <Link href="/contact" onClick={() => setMenuOpen(false)}>Contact<span aria-hidden="true">↗</span></Link>
          </nav>
          {clerkConfigured && <div className="mobile-menu-auth"><HeaderAuth /></div>}
          <p className="menu-note">Furniture. For everyday life.</p>
        </DialogContent>
      </Dialog>
    </div>
  </header>;
}
