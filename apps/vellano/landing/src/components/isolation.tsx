import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";
import { site } from "@/lib/site";

export function Isolation() {
  return (
    <section id="isolation" className="scroll-mt-16 border-b border-line bg-paper-2">
      <div className="mx-auto max-w-[99rem] px-4 py-16 sm:px-8 sm:py-20 lg:grid lg:grid-cols-2 lg:gap-16">
        <Reveal>
          <SectionHeading
            number="01"
            eyebrow="Isolation"
            title="A company is a database, not a column."
            lede="Shared-app multi-tenancy usually means one Postgres and a company_id on every table. That is cheaper. It is also how a missed WHERE clause becomes someone else’s debtor list. We did not take that trade."
          />
        </Reveal>
        <Reveal delay={0.06} className="mt-10 lg:mt-0">
          <dl className="divide-y divide-line border-y border-line bg-white">
            <Row term="Hostname" def={`acme.${site.domain} opens only Acme. An unknown host returns 404, not the first company in the table.`} />
            <Row term="Database" def="CREATE DATABASE per company, its own role, migrations to the same schema head. Vellano’s rows are not queryable from Acme’s session." />
            <Row term="Cookie" def="Host-only. A vellano_session from one hostname is not sent to another. A replayed cookie with the wrong tenant claim is 401." />
            <Row term="Files" def="Object keys are prefixed per company. Existing Vellano keys stay as they are." />
            <Row term="Cost of this" def="Provisioning takes tens of seconds, not tens of milliseconds. Deploy must migrate every ready database. We accepted both." />
          </dl>
        </Reveal>
      </div>
    </section>
  );
}

function Row({ term, def }: { term: string; def: string }) {
  return (
    <div className="grid gap-2 px-4 py-4 sm:grid-cols-[9rem_1fr] sm:gap-8">
      <dt className="text-sm font-medium">{term}</dt>
      <dd className="text-sm leading-relaxed text-muted">{def}</dd>
    </div>
  );
}
