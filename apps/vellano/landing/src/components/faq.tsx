import { Plus } from "lucide-react";

import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";

const items = [
  {
    q: "Is our operational data in the same database as another company?",
    a: "No. Each company is a Postgres database and a hostname. Requests that cannot be resolved to a tenant return 404. A cookie from another hostname does not open yours.",
  },
  {
    q: "Can warehouse staff sign in without seeing cost or the VAT201?",
    a: "Yes. Permissions are keys on the login. Warehouse, till, and books are separate. Trade customers use a different cookie on the same host; staff and customer tokens are not interchangeable.",
  },
  {
    q: "What posts when a customer pays a deposit?",
    a: "GL 2300 Customer deposits. The remainder tax invoice later moves the balance. The VAT201 draft sees both when they belong on it.",
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
    <section id="faq" className="scroll-mt-16 border-t border-line bg-paper-2">
      <div className="page-wrap section-y lg:grid lg:grid-cols-[minmax(0,22rem)_1fr] lg:gap-16">
        <Reveal>
          <SectionHeading
            number="08"
            eyebrow="Questions"
            title="Before you type a company name."
            lede="If a sentence would be true of any back-office product, it is not on this list."
          />
        </Reveal>
        <div className="mt-10 divide-y divide-line border-y border-line bg-white px-6 lg:mt-0">
          {items.map((it) => (
            <details key={it.q} className="group py-6 [&_summary::-webkit-details-marker]:hidden">
              <summary className="flex cursor-pointer list-none items-start justify-between gap-6 text-left text-lg font-normal transition-colors duration-200 hover:text-interactive">
                <span>{it.q}</span>
                <Plus aria-hidden size={18} className="mt-1 shrink-0 text-interactive transition-transform duration-300 group-open:rotate-45" />
              </summary>
              <p className="faq-answer mt-3 max-w-2xl text-sm leading-relaxed text-muted">{it.a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
