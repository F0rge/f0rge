import Link from "next/link";

import { Wordmark } from "@/components/nav";
import { site } from "@/lib/site";

export function SiteFooter() {
  return (
    <footer className="bg-ink text-white">
      <div className="mx-auto grid max-w-[99rem] gap-10 px-4 py-12 sm:px-8 md:grid-cols-[1.5fr_1fr_1fr_1fr]">
        <div>
          <Wordmark inverted />
          <p className="mt-4 max-w-xs text-sm leading-relaxed text-white/70">{site.tagline}</p>
          <p className="mt-6 text-xs text-white/50">Amounts in ZAR. VAT at 15%. Hosting is outside South Africa.</p>
        </div>
        <FooterCol
          title="Product"
          links={[
            { href: "/#product", label: "Stock & warehouse" },
            { href: "/#product", label: "Till, layby, quotes" },
            { href: "/#product", label: "Books & VAT201" },
            { href: "/#isolation", label: "Database per company" },
          ]}
        />
        <FooterCol
          title="Company"
          links={[
            { href: "/signup", label: "Create a company" },
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
      <div className="border-t border-white/10">
        <div className="mx-auto flex max-w-[99rem] flex-col gap-2 px-4 py-4 text-xs text-white/50 sm:flex-row sm:justify-between sm:px-8">
          <span>
            © {new Date().getFullYear()} {site.name}. Placeholder brand — name pending.
          </span>
          <span>Each company is the responsible party. We operate the software on its instructions.</span>
        </div>
      </div>
    </footer>
  );
}

function FooterCol({ title, links }: { title: string; links: { href: string; label: string }[] }) {
  return (
    <div>
      <h3 className="text-xs font-medium uppercase tracking-[0.16em] text-white/50">{title}</h3>
      <ul className="mt-4 space-y-2">
        {links.map((l) => (
          <li key={l.label}>
            <Link href={l.href} className="text-sm text-white/80 hover:text-white hover:underline">
              {l.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
