import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";

const facts = [
  { k: "ZAR", v: "Home currency, rand rounding, cents where they matter." },
  { k: "15%", v: "VAT built into every price, receipt, and credit note." },
  { k: "VAT201", v: "A draft return you can copy into eFiling, line by line." },
  { k: "WhatsApp", v: "Send invoices and statements where your customers already are." },
];

export function SouthAfrica() {
  return (
    <section id="south-africa" className="scroll-mt-20 bg-ink text-paper">
      <div className="mx-auto max-w-7xl px-5 py-24 sm:px-8 sm:py-32">
        <Reveal>
          <div className="[&_.eyebrow]:text-paper/60 [&_.text-muted]:text-paper/70">
            <SectionHeading
              number="02"
              eyebrow="Made for South Africa"
              title={
                <>
                  Built where the <span className="display-italic">rand</span> and the VAT201 live.
                </>
              }
              lede="Not a US product with a currency switch. The defaults are the ones a Joburg showroom actually needs."
            />
          </div>
        </Reveal>
        <div className="mt-14 grid gap-px overflow-hidden rounded-2xl border border-paper/15 bg-paper/15 sm:grid-cols-2 lg:grid-cols-4">
          {facts.map((f, i) => (
            <Reveal key={f.k} delay={i * 0.06} className="bg-ink p-7">
              <div className="font-display text-4xl mono-num">{f.k}</div>
              <p className="mt-3 text-sm leading-relaxed text-paper/70">{f.v}</p>
            </Reveal>
          ))}
        </div>
        <Reveal className="mt-10 grid gap-6 rounded-2xl border border-paper/15 p-7 md:grid-cols-[auto_1fr] md:items-start">
          <span className="eyebrow !text-terracotta">POPIA, plainly</span>
          <p className="max-w-3xl text-base leading-relaxed text-paper/80">
            Each company is its own <em className="text-paper">responsible party</em>. We operate the software for you as the
            operator. Hosting is <em className="text-paper">outside South Africa</em> — we tell you that before you sign up, not in a
            footnote after. Your data sits in a database that only your company&rsquo;s workspace can reach.
          </p>
        </Reveal>
      </div>
    </section>
  );
}
