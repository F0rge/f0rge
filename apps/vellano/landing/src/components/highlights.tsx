import { MessageSquareText, Store } from "lucide-react";

import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";

export function Highlights() {
  return (
    <section id="more" className="scroll-mt-16 border-t border-line bg-paper-2">
      <div className="mx-auto max-w-[99rem] px-4 py-16 sm:px-8 sm:py-20">
        <Reveal>
          <SectionHeading
            number="05"
            eyebrow="Also in the workspace"
            title="Trade customers log in on your hostname. Nia reads your books, not a demo set."
          />
        </Reveal>
        <div className="mt-12 grid gap-px bg-line lg:grid-cols-2">
          <Reveal>
            <Feature
              icon={<Store size={18} />}
              title="Trade portal"
              body="You invite a customer. They see your catalogue at their prices on your address — not a generic storefront. Orders arrive as draft sales orders for someone with permission to confirm. If they should not see cost, they do not."
            >
              <div className="grid grid-cols-3 gap-px bg-line text-[11px]">
                {[
                  ["SKU-4412", "R 14 500"],
                  ["SKU-2201", "R 12 990"],
                  ["SKU-7740", "R 1 890"],
                ].map(([n, p]) => (
                  <div key={n} className="bg-white p-2">
                    <div className="aspect-[4/3] bg-paper-2" />
                    <div className="mt-2 font-medium">{n}</div>
                    <div className="text-muted mono-num">{p}</div>
                  </div>
                ))}
              </div>
            </Feature>
          </Reveal>
          <Reveal delay={0.06}>
            <Feature
              icon={<MessageSquareText size={18} />}
              title="Nia"
              body="Ask which laybys are past 90 days, which SKUs are under minimum, who is over 60 on AR. It answers from this company’s ledger. Caps apply; it is not an unbounded chat bill. If OpenRouter is unset, the UI says so instead of failing quietly."
            >
              <div className="space-y-2 text-[12px]">
                <Bubble who="you">Which laybys are overdue?</Bubble>
                <Bubble who="nia">Three past 90 days: LB-221 (R 4 200), LB-234 (R 1 950), LB-240 (R 7 800). Reminder drafts are ready if you want them sent.</Bubble>
              </div>
            </Feature>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

function Feature({ icon, title, body, children }: { icon: React.ReactNode; title: string; body: string; children: React.ReactNode }) {
  return (
    <article className="grid gap-6 bg-white p-6 sm:p-8 md:grid-cols-[1fr_1fr]">
      <div>
        <span className="grid h-10 w-10 place-items-center bg-ink text-white">{icon}</span>
        <h3 className="mt-5 text-xl font-medium">{title}</h3>
        <p className="mt-3 text-sm leading-relaxed text-muted">{body}</p>
      </div>
      <div className="border border-line bg-paper-2 p-4">{children}</div>
    </article>
  );
}

function Bubble({ who, children }: { who: "you" | "nia"; children: React.ReactNode }) {
  const you = who === "you";
  return (
    <div className={`flex ${you ? "justify-end" : "justify-start"}`}>
      <p className={`max-w-[90%] px-3 py-2 leading-relaxed ${you ? "bg-ink text-white" : "border border-line bg-white"}`}>{children}</p>
    </div>
  );
}
