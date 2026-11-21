"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, ShoppingBag, User } from "lucide-react";
import { Button, Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@f0rge/ui";
import { SHOP_CATEGORIES } from "@/lib/shop-categories";
import { HeaderAuth } from "./header-auth";
import { Wordmark } from "./wordmark";

const links = [
  ...SHOP_CATEGORIES.map(({ name, href }) => ({ label: name, href })),
  { label: "Shop all", href: "/shop" },
  { label: "Help", href: "/help" },
];

export function SiteHeader({ clerkConfigured }: { clerkConfigured: boolean }) {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const current = (href: string) => (pathname === href ? "page" : undefined);

  return <>
    <div className="bg-muted">
      <p className="mx-auto max-w-[1400px] px-4 py-3 text-center text-sm md:px-6">
        <Link href="/#visit" className="font-semibold underline-offset-4 hover:underline">Visit our showroom at Bedford Square, Bedfordview.</Link>
        <span className="hidden sm:inline"> Open seven days a week.</span>
      </p>
    </div>
    <header className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="mx-auto flex h-16 max-w-[1400px] items-center gap-4 px-4 md:px-6">
        <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
          <SheetTrigger render={<Button variant="ghost" size="icon-lg" className="-ml-2 lg:hidden" aria-label="Open menu" />}>
            <Menu className="size-5" />
          </SheetTrigger>
          <SheetContent side="left">
            <SheetHeader>
              <SheetTitle><Wordmark className="text-2xl" /></SheetTitle>
            </SheetHeader>
            <nav aria-label="Mobile navigation" className="grid gap-1 px-4">
              {[...links, { label: "Account", href: "/account" }].map((link) => <Link key={link.href} href={link.href} onClick={() => setMenuOpen(false)} aria-current={current(link.href)} className="rounded-md px-3 py-2.5 text-sm font-medium hover:bg-muted aria-[current=page]:bg-muted">{link.label}</Link>)}
            </nav>
            {clerkConfigured && <div className="flex flex-wrap gap-2 px-4 text-sm"><HeaderAuth /></div>}
          </SheetContent>
        </Sheet>

        <Link href="/" className="text-2xl" aria-label="DasKasas home"><Wordmark /></Link>

        <nav aria-label="Main navigation" className="ml-6 hidden items-center gap-6 lg:flex">
          {links.map((link) => <Link key={link.href} href={link.href} aria-current={current(link.href)} className="text-sm font-medium whitespace-nowrap text-muted-foreground transition-colors hover:text-foreground aria-[current=page]:text-foreground">{link.label}</Link>)}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <div className="hidden items-center gap-2 text-sm lg:flex">
            <Button variant="ghost" size="icon-lg" nativeButton={false} role="link" render={<Link href="/account" aria-label="Account" aria-current={pathname.startsWith("/account") ? "page" : undefined} />}>
              <User className="size-5" />
            </Button>
            {clerkConfigured && <HeaderAuth />}
          </div>
          <Button variant="outline" size="icon-lg" nativeButton={false} role="link" render={<Link href="/bag" aria-label="Bag" aria-current={current("/bag")} />}>
            <ShoppingBag className="size-5" />
          </Button>
        </div>
      </div>
    </header>
  </>;
}
