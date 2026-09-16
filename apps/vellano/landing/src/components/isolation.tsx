import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";
import { site } from "@/lib/site";

export function Isolation() {
  return (
    <section id="isolation" className="scroll-mt-16 border-b border-line bg-paper-2">
      <div className="page-wrap section-y lg:grid lg:grid-cols-2 lg:gap-16">
        <Reveal>
          <SectionHeading
            number="02"
            eyebrow="Isolation"
            title="A company is a database, not a column."
            lede="The usual cheaper design is one Postgres and a company_id on every table. A missed WHERE clause then returns someone else’s debtor list. Each company here is CREATE DATABASE plus a hostname. Provisioning takes tens of seconds. Deploy has to migrate every ready database. Both of those are accepted costs."
          />
        </Reveal>
        <Reveal delay={0.04} className="mt-10 lg:mt-0">
          <dl className="divide-y divide-line border-y border-line bg-white">
            <Row
              term="Hostname"
              def={`acme.${site.domain} opens only Acme. An unknown host returns 404, not the first company in a table.`}
            />
            <Row
              term="Database"
              def="Own role, own database, migrations to the same schema head. Vellano’s rows are not queryable from another company’s session."
            />
            <Row
              term="Cookie"
              def="Host-only. A session from one hostname is not sent to another. A replayed cookie with the wrong company claim is 401."
            />
            <Row term="Files" def="Object keys are prefixed per company. Existing Vellano keys stay as they are." />
            <Row
              term="Fail closed"
              def="No default company. If the host cannot be resolved, the request does not fall through to company one."
            />
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
