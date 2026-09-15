import { ButtonLink } from "@/components/button";
import { Reveal } from "@/components/reveal";
import { WorkspaceMock } from "@/components/workspace-mock";

export function Hero() {
  return (
    <section className="border-b border-line bg-paper">
      <div className="page-wrap grid gap-12 py-12 lg:grid-cols-16 lg:gap-8 lg:py-16">
        <Reveal className="lg:col-span-6">
          <p className="eyebrow">South Africa · ZAR · 15% VAT</p>
          <h1 className="type-display mt-4 text-[2.25rem] sm:text-[3.375rem]">
            Warehouse quantities and the VAT201 draft come from the same ledger.
          </h1>
          <p className="mt-5 max-w-xl text-base leading-relaxed text-muted">
            If the catalogue, the warehouse, and the books are three products, month-end is a reconstruction. Here an
            accepted quote holds stock at a location. Pick, pack, load, and deliver are named states — skip one and the next
            is blocked. The tax invoice reads that ledger. So does the VAT201 draft. We do not file it with SARS.
          </p>
          <div className="mt-8 flex flex-wrap">
            <ButtonLink href="/signup">Create a company workspace</ButtonLink>
            <ButtonLink href="/#sale" variant="ghost">
              How a sale moves
            </ButtonLink>
          </div>
          <p className="mt-4 text-sm text-muted">
            No charge while the first companies onboard. At least 60 days&rsquo; notice before a price. Nothing is
            provisioned until the owner verifies email.
          </p>
        </Reveal>
        <Reveal delay={0.06} className="lg:col-span-10">
          <WorkspaceMock />
        </Reveal>
      </div>
      <dl className="grid border-t border-line sm:grid-cols-2 lg:grid-cols-4 lg:divide-x lg:divide-line">
        {[
          ["Isolation", "One Postgres database and hostname per company."],
          ["Documents", "Quote → sales order → pick/pack/deliver → tax invoice."],
          ["Books", "GL 2300 for deposits. 15% VAT on the line. VAT201 is a draft."],
          ["In use", "Vellano is company one — own database, not a row in a shared table."],
        ].map(([k, v]) => (
          <div key={k} className="border-b border-line px-4 py-5 sm:px-8 lg:border-b-0">
            <dt className="text-sm font-medium">{k}</dt>
            <dd className="mt-1 text-sm text-muted">{v}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
