import { ButtonLink } from "@/components/button";
import { Reveal } from "@/components/reveal";
import { WorkspaceMock } from "@/components/workspace-mock";

export function Hero() {
  return (
    <section className="border-b border-line bg-paper">
      <div className="page-wrap grid gap-12 py-20 lg:grid-cols-16 lg:items-center lg:gap-12 lg:py-28">
        <Reveal className="lg:col-span-6">
          <h1 className="type-display text-[2.5rem] sm:text-[3.75rem]">Company software, built for humans.</h1>
          <p className="mt-6 max-w-xl text-base leading-relaxed text-muted sm:text-lg">
            If the catalogue, the warehouse, and the books are three products, month-end is a reconstruction. Here an
            accepted quote holds stock at a location. Pick, pack, load, and deliver are named states — skip one and the next
            is blocked. The tax invoice reads that ledger. So does the VAT201 draft.
          </p>
          <div className="mt-10 flex flex-wrap gap-0">
            <ButtonLink href="/signup">Create a company workspace</ButtonLink>
            <ButtonLink href="/#sale" variant="ghost">
              How a sale moves
            </ButtonLink>
          </div>
        </Reveal>
        <Reveal delay={0.12} className="lg:col-span-10">
          <WorkspaceMock />
        </Reveal>
      </div>
      <div className="border-t border-line">
        <dl className="page-wrap grid sm:grid-cols-2 lg:grid-cols-4 lg:divide-x lg:divide-line">
          {[
            ["Isolation", "One Postgres database and hostname per company."],
            ["Documents", "Quote → sales order → pick/pack/deliver → tax invoice."],
            ["Books", "GL 2300 for deposits. 15% VAT on the line. VAT201 is a draft."],
            ["In use", "Vellano is company one — own database, not a row in a shared table."],
          ].map(([k, v], i) => (
            <Reveal key={k} delay={0.04 * i} className="border-b border-line py-8 last:border-b-0 sm:px-2 lg:border-b-0 lg:px-8 lg:first:pl-0 lg:last:pr-0">
              <dt className="text-sm font-medium">{k}</dt>
              <dd className="mt-2 text-sm leading-relaxed text-muted">{v}</dd>
            </Reveal>
          ))}
        </dl>
      </div>
    </section>
  );
}
