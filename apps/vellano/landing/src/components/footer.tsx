import Link from "next/link";

import { Wordmark } from "@/components/nav";
import { site } from "@/lib/site";

export function SiteFooter() {
  return (
    <footer className="border-t border-[#393939] bg-ink text-white">
      <div className="page-wrap grid gap-10 py-16 md:grid-cols-[1.5fr_1fr_1fr_1fr]">
        <div>
          <Wordmark inverted />
          <p className="mt-4 max-w-xs text-sm leading-relaxed text-[#c6c6c6]">{site.tagline}</p>
          <p className="mt-6 text-xs text-[#8d8d8d]">Amounts in ZAR. VAT at 15%. Hosting is in the United States.</p>
        </div>
        <FooterCol
          title="Product"
          links={[
            { href: "/#product", label: "Stock and warehouse" },
            { href: "/#product", label: "Till, layby, quotes" },
            { href: "/#product", label: "Books and VAT201" },
            { href: "/#company", label: "Roles and documents" },
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
      <div className="border-t border-[#393939]">
        <div className="page-wrap flex flex-col gap-2 py-4 text-xs text-[#8d8d8d] sm:flex-row sm:justify-between">
          <span>
            © {new Date().getFullYear()} {site.name}. Each company is the responsible party.
          </span>
          <span>We operate the software on the company’s instructions.</span>
        </div>
      </div>
    </footer>
  );
}

function FooterCol({ title, links }: { title: string; links: { href: string; label: string }[] }) {
  return (
    <div>
      <h3 className="text-xs font-normal uppercase tracking-[0.16em] text-[#8d8d8d]">{title}</h3>
      <ul className="mt-4 space-y-2">
        {links.map((l) => (
          <li key={l.label}>
            <Link href={l.href} className="text-sm text-[#c6c6c6] transition-colors duration-200 hover:text-white hover:underline">
              {l.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
