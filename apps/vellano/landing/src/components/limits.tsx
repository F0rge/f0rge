import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";

const points = [
  {
    title: "You do not hold stock",
    body: "Agencies, consultancies, and pure dropship without a location will spend their time fighting empty warehouses. Use something thinner.",
  },
  {
    title: "You need a custom domain on day one",
    body: "shop.yourco.co.za is on the registry later. v1 is slug.stockroom.example. If that is a blocker for the board, wait.",
  },
  {
    title: "You want us to be the responsible party",
    body: "We operate the software. Your company remains the responsible party under POPIA. We will not take that hat.",
  },
  {
    title: "You need billing, SSO, or a second company’s memberships today",
    body: "No Stripe. No Google login. One email can exist in two tenant databases because users are per database; the public signup does not manage that for you.",
  },
];

export function Limits() {
  return (
    <section id="limits" className="scroll-mt-16 border-t border-line bg-paper-2">
      <div className="mx-auto max-w-[99rem] px-4 py-16 sm:px-8 sm:py-20">
        <Reveal>
          <SectionHeading
            number="06"
            eyebrow="Not this product"
            title="Four reasons to close the tab."
            lede="A page that tries to keep everyone reads like it was written for no one. These are the stops we already know."
          />
        </Reveal>
        <ol className="mt-12 grid gap-px bg-line sm:grid-cols-2">
          {points.map((p, i) => (
            <Reveal key={p.title} delay={i * 0.04} className="bg-white p-6 sm:p-8">
              <span className="font-mono text-sm text-muted">{String(i + 1).padStart(2, "0")}</span>
              <h3 className="mt-3 text-lg font-medium">{p.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">{p.body}</p>
            </Reveal>
          ))}
        </ol>
      </div>
    </section>
  );
}
