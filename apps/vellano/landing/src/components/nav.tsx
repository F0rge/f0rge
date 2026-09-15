"use client";

import { Menu, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { ButtonLink } from "@/components/button";
import { site } from "@/lib/site";

const links = [
  { href: "/#product", label: "Product" },
  { href: "/#isolation", label: "Isolation" },
  { href: "/#south-africa", label: "South Africa" },
  { href: "/#how", label: "Onboarding" },
  { href: "/#faq", label: "Pricing" },
];

export function Wordmark({ className = "", inverted = false }: { className?: string; inverted?: boolean }) {
  return (
    <Link href="/" className={`inline-flex items-center gap-2 ${className}`} aria-label={`${site.name} home`}>
      <span aria-hidden className={`grid h-6 w-6 place-items-center ${inverted ? "bg-white" : "bg-ink"}`}>
        <span className={`block h-3 w-3 border-2 ${inverted ? "border-ink" : "border-white"}`} />
      </span>
      <span className="text-[1.125rem] font-semibold leading-none tracking-tight">{site.name}</span>
    </Link>
  );
}

export function SiteNav() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <header className="sticky top-0 z-40 bg-ink text-white">
      <nav className="mx-auto flex h-12 max-w-[99rem] items-center justify-between px-4 sm:px-8" aria-label="Main">
        <Wordmark inverted />
        <ul className="hidden h-12 items-stretch md:flex">
          {links.map((l) => (
            <li key={l.href} className="flex">
              <Link href={l.href} className="flex items-center px-4 text-sm text-white/80 hover:bg-white/10 hover:text-white">
                {l.label}
              </Link>
            </li>
          ))}
        </ul>
        <div className="hidden items-center md:flex">
          <Link href="/signin" className="flex h-12 items-center px-4 text-sm text-white/80 hover:bg-white/10 hover:text-white">
            Sign in
          </Link>
          <ButtonLink href="/signup" variant="header">
            Create a company
          </ButtonLink>
        </div>
        <button
          type="button"
          className="grid h-12 w-12 place-items-center md:hidden"
          aria-expanded={open}
          aria-controls="mobile-menu"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </nav>
      {open ? (
        <div id="mobile-menu" className="border-t border-white/10 bg-ink px-4 pb-6 pt-2 md:hidden">
          <ul>
            {links.map((l) => (
              <li key={l.href}>
                <Link href={l.href} onClick={() => setOpen(false)} className="block py-3 text-base hover:text-white/70">
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
          <div className="mt-4 flex flex-col gap-2">
            <ButtonLink href="/signup" variant="header" onClick={() => setOpen(false)}>
              Create a company
            </ButtonLink>
            <ButtonLink href="/signin" variant="secondary" onClick={() => setOpen(false)}>
              Sign in
            </ButtonLink>
          </div>
        </div>
      ) : null}
    </header>
  );
}
