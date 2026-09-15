"use client";

import { Menu, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { ButtonLink } from "@/components/button";
import { site } from "@/lib/site";

const links = [
  { href: "/#product", label: "Product" },
  { href: "/#south-africa", label: "For SA retailers" },
  { href: "/#how", label: "How it works" },
  { href: "/#faq", label: "Pricing" },
];

export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <Link href="/" className={`inline-flex items-center gap-2.5 ${className}`} aria-label={`${site.name} home`}>
      <span aria-hidden className="grid h-7 w-7 place-items-center rounded-[7px] bg-ink">
        <span className="block h-3.5 w-3.5 border-2 border-paper border-b-terracotta" />
      </span>
      <span className="font-display text-[1.35rem] leading-none tracking-tight">{site.name}</span>
    </Link>
  );
}

export function SiteNav() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <header
      className={`sticky top-0 z-40 border-b transition-colors duration-300 ${
        scrolled ? "border-line bg-paper/85 backdrop-blur-md" : "border-transparent bg-transparent"
      }`}
    >
      <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 sm:px-8" aria-label="Main">
        <Wordmark />
        <ul className="hidden items-center gap-8 md:flex">
          {links.map((l) => (
            <li key={l.href}>
              <Link href={l.href} className="text-sm text-ink-2 transition-colors hover:text-terracotta">
                {l.label}
              </Link>
            </li>
          ))}
        </ul>
        <div className="hidden items-center gap-2 md:flex">
          <ButtonLink href="/signin" variant="ghost">
            Sign in
          </ButtonLink>
          <ButtonLink href="/signup">Create your company</ButtonLink>
        </div>
        <button
          type="button"
          className="grid h-10 w-10 place-items-center rounded-full md:hidden"
          aria-expanded={open}
          aria-controls="mobile-menu"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </nav>
      {open ? (
        <div id="mobile-menu" className="border-t border-line bg-paper px-5 pb-8 pt-4 md:hidden">
          <ul className="flex flex-col gap-1">
            {links.map((l) => (
              <li key={l.href}>
                <Link
                  href={l.href}
                  onClick={() => setOpen(false)}
                  className="block rounded-lg px-3 py-3 font-display text-2xl hover:bg-paper-2"
                >
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
          <div className="mt-6 flex flex-col gap-2">
            <ButtonLink href="/signup" onClick={() => setOpen(false)}>
              Create your company
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
