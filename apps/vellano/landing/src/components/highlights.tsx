import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";

export function Highlights() {
  return (
    <section id="more" className="scroll-mt-16 border-t border-line bg-paper-2">
      <div className="page-wrap py-16 sm:py-20">
        <Reveal>
          <SectionHeading
            number="06"
            eyebrow="Also in the workspace"
            title="Trade customers log in on your hostname. Nia reads this company’s ledger."
          />
        </Reveal>
        <div className="mt-12 grid gap-px bg-line lg:grid-cols-2">
          <Reveal>
            <Feature
              n="01"
              title="Trade portal"
              body="You invite a customer. They see your catalogue at their prices on your address — not a generic storefront. Orders arrive as draft sales orders for someone with permission to confirm. If they should not see cost, they do not."
            >
              <div className="grid grid-cols-3 gap-px bg-line text-[12px]">
                {[
                  ["SKU-4412", "R 14 500"],
                  ["SKU-2201", "R 12 990"],
                  ["SKU-7740", "R 1 890"],
                ].map(([n, p]) => (
                  <div key={n} className="bg-white p-3">
                    <div className="aspect-[4/3] bg-paper-2" />
                    <div className="mt-2 font-medium">{n}</div>
                    <div className="text-muted mono-num">{p}</div>
                  </div>
                ))}
              </div>
            </Feature>
          </Reveal>
          <Reveal delay={0.04}>
            <Feature
              n="02"
              title="Nia"
              body="Questions against this company’s books: laybys past 90 days, SKUs under minimum, debtors over 60. Caps apply; it is not an unbounded chat bill. If the model key is unset, the UI says so instead of failing quietly."
            >
              <dl className="divide-y divide-line border border-line bg-white text-[13px]">
                <div className="grid grid-cols-[7rem_1fr] px-3 py-3">
                  <dt className="text-muted">Ask</dt>
                  <dd>Which laybys are past 90 days?</dd>
                </div>
                <div className="grid grid-cols-[7rem_1fr] px-3 py-3">
                  <dt className="text-muted">From ledger</dt>
                  <dd>LB-221 R 4 200 · LB-234 R 1 950 · LB-240 R 7 800. Reminder drafts if you want them sent.</dd>
                </div>
              </dl>
            </Feature>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

function Feature({ n, title, body, children }: { n: string; title: string; body: string; children: React.ReactNode }) {
  return (
    <article className="grid gap-6 bg-white p-6 sm:p-8 md:grid-cols-2">
      <div>
        <span className="font-mono text-sm text-interactive">{n}</span>
        <h3 className="mt-4 text-xl font-normal">{title}</h3>
        <p className="mt-3 text-sm leading-relaxed text-muted">{body}</p>
      </div>
      <div>{children}</div>
    </article>
  );
}
