import Link from "next/link";
import { SHOP_CATEGORIES } from "@/lib/shop-categories";
import { SHOWROOM } from "@/lib/showroom";
import { CookieSettingsButton } from "./analytics/cookie-settings-button";
import { Wordmark } from "./wordmark";

const columns = [
  { title: "Shop", links: [{ label: "Shop all", href: "/shop" }, ...SHOP_CATEGORIES.map(({ name, href }) => ({ label: name, href }))] },
  { title: "Help", links: [{ label: "Help", href: "/help" }, { label: "Delivery and collection", href: "/policies/delivery" }, { label: "Returns", href: "/policies/returns" }, { label: "Refunds", href: "/policies/refunds" }] },
  { title: "Policies", links: [{ label: "Terms and conditions", href: "/policies/terms" }, { label: "Privacy policy", href: "/policies/privacy" }] },
];

const linkClass = "text-sm text-muted-foreground transition-colors hover:text-foreground";

export function SiteFooter() {
  return <footer className="border-t bg-muted/50 px-4 py-8 md:py-12">
    <div className="mx-auto max-w-7xl">
      <div className="mb-8 md:mb-12">
        <Link href="/" className="inline-block text-3xl" aria-label="DasKasas home"><Wordmark /></Link>
        <p className="mt-2 max-w-md text-sm text-muted-foreground">Furniture for living and dining rooms, from our showroom in Bedford Square, Bedfordview.</p>
      </div>
      <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
        {columns.map((column) => <nav key={column.title} aria-label={column.title} className="space-y-4">
          <h2 className="text-sm font-semibold tracking-wider uppercase">{column.title}</h2>
          <ul className="space-y-3">
            {column.links.map((link) => <li key={link.href}><Link href={link.href} className={linkClass}>{link.label}</Link></li>)}
            {/* Mantine's unlayered reset makes buttons inherit font: size the item, not the button. */}
            {column.title === "Policies" && <li className="text-sm"><CookieSettingsButton className={linkClass} /></li>}
          </ul>
        </nav>)}
        <div className="space-y-4">
          <h2 className="text-sm font-semibold tracking-wider uppercase">Visit us</h2>
          <address className="space-y-3 text-sm text-muted-foreground not-italic">
            <p>{SHOWROOM.address}</p>
            <ul className="space-y-1">{SHOWROOM.hours.map((row) => <li key={row.short}>{row.short} {row.time}</li>)}</ul>
            <ul className="space-y-1">{SHOWROOM.phones.map((phone) => <li key={phone.number}>{phone.label}: {phone.number}</li>)}</ul>
            <p>{SHOWROOM.email}</p>
          </address>
        </div>
      </div>
      <div className="mt-8 flex flex-col gap-4 border-t pt-8 text-xs text-muted-foreground md:flex-row md:items-center md:justify-between">
        <Link href="/help" className="transition-colors hover:text-foreground">Help</Link>
        <p>© {new Date().getFullYear()} DasKasas</p>
      </div>
    </div>
  </footer>;
}
