import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";

const points = [
  {
    title: "You do not hold stock",
    body: "Agencies, consultancies, and pure dropship without a location will spend their time on empty warehouses. Use something thinner.",
  },
  {
    title: "You need a custom domain on day one",
    body: "shop.yourco.co.za is on the registry later. v1 is slug.stockroom.example. If that is a board blocker, wait.",
  },
  {
    title: "You want us to be the responsible party",
    body: "We operate the software. Your company remains the responsible party under POPIA. We will not take that hat.",
  },
  {
    title: "You need billing, SSO, or cross-company memberships today",
    body: "No card on the form. No Google login. One email can exist in two tenant databases because users are per database; public signup does not manage that for you.",
  },
];

export function Limits() {
  return (
    <section id="limits" className="scroll-mt-16 border-t border-line">
      <div className="page-wrap section-y">
        <Reveal>
          <SectionHeading
            number="07"
            eyebrow="Not this product"
            title="Do not create a workspace if any of these are true."
            lede="These are stops we already know. If your case is one of them, wait or use something else — we will not stretch the product to cover it this year."
          />
        </Reveal>
        <ol className="mt-12 grid gap-px bg-line sm:grid-cols-2">
          {points.map((p, i) => (
            <li key={p.title} className="bg-white p-6 sm:p-8">
              <span className="font-mono text-sm text-muted">{String(i + 1).padStart(2, "0")}</span>
              <h3 className="mt-3 text-lg font-normal">{p.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">{p.body}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
