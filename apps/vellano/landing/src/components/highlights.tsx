import { MessageSquareText, Store } from "lucide-react";

import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";

export function Highlights() {
  return (
    <section id="more" className="mx-auto max-w-7xl scroll-mt-20 px-5 pb-24 sm:px-8 sm:pb-32">
      <Reveal>
        <SectionHeading
          number="04"
          eyebrow="Also in the box"
          title={
            <>
              Your customers get a door. <span className="display-italic">You get an assistant.</span>
            </>
          }
        />
      </Reveal>
      <div className="mt-14 grid gap-5 lg:grid-cols-2">
        <Reveal>
          <Feature
            icon={<Store size={20} />}
            title="Trade portal"
            body="Give trade customers their own login on your address. They browse your catalogue at their prices and place orders that land as draft sales orders — no WhatsApp back-and-forth."
          >
            <div className="grid grid-cols-3 gap-2 text-[11px]">
              {["Oak table", "Linen sofa", "Side table"].map((n, i) => (
                <div key={n} className="rounded-lg border border-line bg-white p-2">
                  <div className="aspect-[4/3] rounded-md bg-paper-3" />
                  <div className="mt-2 font-medium">{n}</div>
                  <div className="text-muted mono-num">R {[14500, 12990, 1890][i].toLocaleString("en-ZA")}</div>
                </div>
              ))}
            </div>
          </Feature>
        </Reveal>
        <Reveal delay={0.08}>
          <Feature
            icon={<MessageSquareText size={20} />}
            title="Nia, the back-office assistant"
            body="Ask what sold last week, which SKUs are under minimum, or who owes more than 60 days. Nia answers from your books and can draft the follow-ups."
          >
            <div className="space-y-2 text-[12px]">
              <Bubble who="you">Which laybys are overdue?</Bubble>
              <Bubble who="nia">3 laybys past 90 days: LB-221 (R 4 200), LB-234 (R 1 950), LB-240 (R 7 800). Want reminder messages drafted?</Bubble>
            </div>
          </Feature>
        </Reveal>
      </div>
    </section>
  );
}

function Feature({ icon, title, body, children }: { icon: React.ReactNode; title: string; body: string; children: React.ReactNode }) {
  return (
    <article className="grid h-full gap-6 rounded-2xl border border-line bg-white/60 p-7 md:grid-cols-[1fr_1fr]">
      <div>
        <span className="grid h-10 w-10 place-items-center rounded-full bg-ink text-paper">{icon}</span>
        <h3 className="mt-5 text-2xl">{title}</h3>
        <p className="mt-3 text-sm leading-relaxed text-muted">{body}</p>
      </div>
      <div className="rounded-xl border border-line bg-paper p-4">{children}</div>
    </article>
  );
}

function Bubble({ who, children }: { who: "you" | "nia"; children: React.ReactNode }) {
  const you = who === "you";
  return (
    <div className={`flex ${you ? "justify-end" : "justify-start"}`}>
      <p className={`max-w-[85%] rounded-2xl px-3 py-2 leading-relaxed ${you ? "bg-ink text-paper" : "border border-line bg-white"}`}>{children}</p>
    </div>
  );
}
