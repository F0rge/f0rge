import { Plus } from "lucide-react";

import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";

const items = [
  {
    q: "Is our data separate from other companies?",
    a: "Yes. Every company gets its own database and its own address. Requests that cannot be tied to your workspace are refused outright — there is no shared table with a company column.",
  },
  {
    q: "Can our trade customers log in?",
    a: "Yes. The trade portal runs on your address. You invite a customer, they see your catalogue at their prices, and their orders arrive as draft sales orders for you to confirm.",
  },
  {
    q: "Do you charge yet?",
    a: "Not yet. Creating a company is free while we onboard the first retailers. When pricing arrives it will be per company, in rand, with notice before anything changes.",
  },
  {
    q: "Where is our data hosted?",
    a: "Outside South Africa, on managed infrastructure in the United States, with encrypted backups. Under POPIA your company is the responsible party and we act as operator — the notice you accept at signup spells this out.",
  },
  {
    q: "Can we import from Cin7 or Xero?",
    a: "Yes. After signup, the owner settings page has CSV imports for SKUs, customers, suppliers, and opening balances, plus Cin7 and Xero shaped templates.",
  },
];

export function Faq() {
  return (
    <section id="faq" className="scroll-mt-20 border-t border-line bg-paper-2/60">
      <div className="mx-auto max-w-7xl px-5 py-24 sm:px-8 sm:py-32 lg:grid lg:grid-cols-[1fr_1.4fr] lg:gap-16">
        <Reveal>
          <SectionHeading number="05" eyebrow="Questions" title={<>Straight answers.</>} lede="Pricing, hosting, and what happens to your data — the things people ask before they type a company name." />
        </Reveal>
        <div className="mt-12 divide-y divide-line border-y border-line lg:mt-0">
          {items.map((it, i) => (
            <Reveal key={it.q} delay={i * 0.04}>
              <details className="group py-5 [&_summary::-webkit-details-marker]:hidden">
                <summary className="flex cursor-pointer list-none items-start justify-between gap-6 text-left font-display text-xl sm:text-2xl">
                  <span>{it.q}</span>
                  <Plus aria-hidden size={20} className="mt-1 shrink-0 text-terracotta transition-transform duration-300 group-open:rotate-45" />
                </summary>
                <p className="mt-3 max-w-2xl text-base leading-relaxed text-muted">{it.a}</p>
              </details>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
