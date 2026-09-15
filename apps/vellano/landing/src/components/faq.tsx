import { Plus } from "lucide-react";

import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";

const items = [
  {
    q: "Is our operational data in the same database as another company?",
    a: "No. Each company is a Postgres database and a hostname. Requests that cannot be resolved to a tenant return 404. A cookie from another hostname does not open yours.",
  },
  {
    q: "Can trade customers log in?",
    a: "On your hostname, with a separate session cookie. They see catalogue at their prices and place draft sales orders. Staff tokens and customer tokens are not interchangeable.",
  },
  {
    q: "What does it cost?",
    a: "Nothing while we onboard the first companies. When a price exists it will be per company, in rand, with at least 60 days’ notice to workspaces already running. There is no card on the signup form.",
  },
  {
    q: "Where is data hosted, and who is the responsible party?",
    a: "Managed infrastructure in the United States. Under POPIA the company is the responsible party and we act as operator. Cross-border transfer is disclosed before signup. We notify you of a breach so you can notify the Regulator.",
  },
  {
    q: "Can we bring SKUs from Cin7 or Xero?",
    a: "CSV templates in owner settings after you are in — SKUs, customers, suppliers, opening balances. There is no live two-way sync on day one. If you need that before you move, wait; do not import twice.",
  },
];

export function Faq() {
  return (
    <section id="faq" className="scroll-mt-16 border-t border-line">
      <div className="mx-auto max-w-[99rem] px-4 py-16 sm:px-8 sm:py-20 lg:grid lg:grid-cols-[minmax(0,22rem)_1fr] lg:gap-16">
        <Reveal>
          <SectionHeading
            number="07"
            eyebrow="Questions"
            title="The things people ask before they type a company name."
            lede="If a sentence would be true of any back-office product, it is not on this list."
          />
        </Reveal>
        <div className="mt-10 divide-y divide-line border-y border-line lg:mt-0">
          {items.map((it, i) => (
            <Reveal key={it.q} delay={i * 0.03}>
              <details className="group py-5 [&_summary::-webkit-details-marker]:hidden">
                <summary className="flex cursor-pointer list-none items-start justify-between gap-6 text-left text-lg font-medium sm:text-xl">
                  <span>{it.q}</span>
                  <Plus aria-hidden size={18} className="mt-1 shrink-0 text-interactive transition-transform duration-200 group-open:rotate-45" />
                </summary>
                <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted sm:text-base">{it.a}</p>
              </details>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
