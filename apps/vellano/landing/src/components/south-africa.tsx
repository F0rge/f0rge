import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";

const facts = [
  { k: "ZAR", v: "Home currency. Cents where the document needs them; rand rounding where SARS does." },
  { k: "15%", v: "VAT on the line of the quote, the till slip, the credit note. Not a plugin you remember in December." },
  { k: "VAT201", v: "A draft return, boxes filled from the ledger, for you to copy into eFiling. We do not submit it." },
  { k: "WhatsApp", v: "Invoices and statements on the channel the order often already used. SMTP still works." },
];

export function SouthAfrica() {
  return (
    <section id="south-africa" className="scroll-mt-16 bg-ink text-white">
      <div className="mx-auto max-w-[99rem] px-4 py-16 sm:px-8 sm:py-20">
        <Reveal>
          <div className="[&_.eyebrow]:text-white/50 [&_.text-muted]:text-white/70">
            <SectionHeading
              number="03"
              eyebrow="Defaults"
              title="Rand first. VAT on the line. eFiling is still yours."
              lede="A US product with a currency dropdown still thinks in dollars and then translates. The documents here are written as if the company is already a VAT vendor."
            />
          </div>
        </Reveal>
        <div className="mt-12 grid gap-px bg-white/10 sm:grid-cols-2 lg:grid-cols-4">
          {facts.map((f, i) => (
            <Reveal key={f.k} delay={i * 0.04} className="bg-ink p-6">
              <div className="font-serif text-3xl mono-num">{f.k}</div>
              <p className="mt-3 text-sm leading-relaxed text-white/70">{f.v}</p>
            </Reveal>
          ))}
        </div>
        <Reveal className="mt-10 grid gap-4 border border-white/15 p-6 md:grid-cols-[8rem_1fr]">
          <span className="eyebrow !text-white/50">POPIA</span>
          <p className="max-w-3xl text-sm leading-relaxed text-white/80">
            The company that owns the workspace is the responsible party. We are the operator. Hosting is outside South Africa;
            that is stated on the signup form, not in a footer after the fact. We will sign a written operator agreement on
            request.
          </p>
        </Reveal>
      </div>
    </section>
  );
}
