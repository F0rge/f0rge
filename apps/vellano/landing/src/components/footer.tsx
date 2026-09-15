import Link from "next/link";

import { Wordmark } from "@/components/nav";
import { site } from "@/lib/site";

export function SiteFooter() {
  return (
    <footer className="border-t border-line bg-paper-2/60">
      <div className="mx-auto grid max-w-7xl gap-10 px-5 py-14 sm:px-8 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
        <div>
          <Wordmark />
          <p className="mt-4 max-w-xs text-sm leading-relaxed text-muted">{site.tagline}</p>
          <p className="mt-6 text-xs text-muted">
            Built in Johannesburg. Prices in ZAR. VAT at 15%.
          </p>
        </div>
        <FooterCol
          title="Product"
          links={[
            { href: "/#product", label: "Stock & warehouse" },
            { href: "/#product", label: "Till, layby & quotes" },
            { href: "/#product", label: "Books & VAT201" },
            { href: "/#more", label: "Trade portal & Nia" },
          ]}
        />
        <FooterCol
          title="Company"
          links={[
            { href: "/signup", label: "Create your company" },
            { href: "/signin", label: "Sign in" },
            { href: `mailto:${site.supportEmail}`, label: site.supportEmail },
          ]}
        />
        <FooterCol
          title="Legal"
          links={[
            { href: "/legal/privacy", label: "Privacy notice" },
            { href: "/legal/popia", label: "POPIA notice" },
            { href: "/legal/terms", label: "Terms" },
          ]}
        />
      </div>
      <div className="border-t border-line">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-5 py-5 text-xs text-muted sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <span>© {new Date().getFullYear()} {site.name}. Placeholder brand — name pending.</span>
          <span>Each company is its own responsible party. We operate the software on your behalf.</span>
        </div>
      </div>
    </footer>
  );
}

function FooterCol({ title, links }: { title: string; links: { href: string; label: string }[] }) {
  return (
    <div>
      <h3 className="font-sans text-xs font-medium uppercase tracking-[0.18em] text-muted">{title}</h3>
      <ul className="mt-4 space-y-2.5">
        {links.map((l) => (
          <li key={l.label}>
            <Link href={l.href} className="text-sm text-ink-2 hover:text-terracotta">
              {l.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
