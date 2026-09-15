import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";

const facts = [
  { k: "ZAR", v: "Home currency. Cents where the document needs them; rand rounding where SARS does." },
  { k: "15%", v: "VAT on the line of the quote, the till slip, and the credit note. Not a year-end adjustment." },
  { k: "VAT201", v: "A draft return, boxes filled from the ledger, for you to copy into eFiling. We do not submit it." },
  { k: "WhatsApp", v: "Invoices and statements on the channel the order often already used. SMTP still works." },
];

export function SouthAfrica() {
  return (
    <section id="south-africa" className="scroll-mt-16 bg-ink text-white">
      <div className="page-wrap py-16 sm:py-20">
        <Reveal>
          <div className="[&_.eyebrow]:text-[#c6c6c6] [&_.text-muted]:text-[#c6c6c6]">
            <SectionHeading
              number="04"
              eyebrow="Defaults"
              title="Rand first. VAT on the line. eFiling stays yours."
              lede="Documents are written as if the company is already a VAT vendor. A currency dropdown on a US product still thinks in dollars and then converts."
            />
          </div>
        </Reveal>
        <div className="mt-12 grid gap-px bg-white/10 sm:grid-cols-2 lg:grid-cols-4">
          {facts.map((f) => (
            <div key={f.k} className="bg-ink p-6">
              <div className="font-light text-3xl mono-num">{f.k}</div>
              <p className="mt-3 text-sm leading-relaxed text-[#c6c6c6]">{f.v}</p>
            </div>
          ))}
        </div>
        <div className="mt-10 grid gap-4 border border-white/15 p-6 md:grid-cols-[8rem_1fr]">
          <span className="eyebrow !text-[#8d8d8d]">POPIA</span>
          <p className="max-w-3xl text-sm leading-relaxed text-[#c6c6c6]">
            The company that owns the workspace is the responsible party. We are the operator. Hosting is in the United
            States; that is stated on the signup form, not only in a footer. We will sign a written operator agreement on
            request. On a breach we notify the company so it can notify the Regulator.
          </p>
        </div>
      </div>
    </section>
  );
}
