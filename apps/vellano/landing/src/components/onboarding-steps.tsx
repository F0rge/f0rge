import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";
import { site } from "@/lib/site";

const examples = ["acme", "northridge", "harbour-co"];

export function OnboardingSteps() {
  return (
    <section id="how" className="scroll-mt-16">
      <div className="page-wrap section-y">
        <Reveal>
          <SectionHeading
            number="05"
            eyebrow="Onboarding"
            title="Email first. Database second."
            lede="A signup that immediately provisions compute is how you get empty spam companies. We wait for the verify click. Then: a role, a database, migrations, one owner. No default till passwords, no sample locations."
          />
        </Reveal>
        <ol className="mt-12 grid gap-px bg-line md:grid-cols-3">
          <Step
            n="1"
            title="Company details"
            body="Legal name, optional trading name, the hostname you want, owner email and password. Two acknowledgements: you may bind the company, and you have read that hosting is outside South Africa."
          />
          <Step n="2" title="Verify email" body="One link, 24 hours, single use. Until you click it there is no database and no workspace. Resend is capped." />
          <Step
            n="3"
            title="Empty workspace"
            body="Owner login only. Import SKUs or start from zero. Cin7 and Xero shaped CSVs are in settings."
          >
            <ul className="mt-5 border border-line bg-paper-2 font-mono text-sm">
              {examples.map((slug) => (
                <li key={slug} className="border-b border-line px-3 py-2 last:border-0">
                  <span className="text-muted">https://</span>
                  {slug}
                  <span className="text-muted">.{site.domain}</span>
                </li>
              ))}
            </ul>
          </Step>
        </ol>
      </div>
    </section>
  );
}

function Step({ n, title, body, children }: { n: string; title: string; body: string; children?: React.ReactNode }) {
  return (
    <Reveal as="li" delay={(Number(n) - 1) * 0.04} className="bg-white p-6 sm:p-8">
      <span className="font-mono text-sm text-interactive">{n}</span>
      <h3 className="mt-4 text-xl font-normal">{title}</h3>
      <p className="mt-3 text-sm leading-relaxed text-muted">{body}</p>
      {children}
    </Reveal>
  );
}
