import { ArrowRight } from "lucide-react";

import { ButtonLink } from "@/components/button";
import { Reveal } from "@/components/reveal";
import { WorkspaceMock } from "@/components/workspace-mock";

export function Hero() {
  return (
    <section className="border-b border-line bg-paper-2">
      <div className="mx-auto grid max-w-[99rem] gap-10 px-4 py-16 sm:px-8 lg:grid-cols-[minmax(0,28rem)_1fr] lg:items-start lg:py-20">
        <Reveal>
          <p className="eyebrow">South Africa · ZAR · 15% VAT</p>
          <h1 className="mt-4 font-serif text-4xl leading-[1.15] sm:text-5xl">
            The warehouse and the VAT201 should be looking at the same stock.
          </h1>
          <p className="mt-5 text-base leading-relaxed text-muted sm:text-lg">
            Catalogue in one product, warehouse in another, books in a third: month-end is a reconstruction. Here a quote that is
            accepted holds stock, a delivery can be invoiced, and the VAT201 draft is a read of that ledger.
          </p>
          <div className="mt-8 flex flex-wrap gap-0">
            <ButtonLink href="/signup">
              Create a company workspace <ArrowRight size={16} />
            </ButtonLink>
            <ButtonLink href="/#sale" variant="secondary">
              How a sale moves
            </ButtonLink>
          </div>
          <p className="mt-4 text-sm text-muted">
            No charge while we onboard the first companies. 60 days&rsquo; notice before a price. We do not create a database until the
            owner verifies email.
          </p>
          <p className="mt-6 border-l-4 border-interactive pl-3 text-sm text-muted">
            In use at Vellano — company one, on its own database, not a row in a shared table.
          </p>
        </Reveal>
        <Reveal delay={0.08}>
          <WorkspaceMock />
        </Reveal>
      </div>
    </section>
  );
}
