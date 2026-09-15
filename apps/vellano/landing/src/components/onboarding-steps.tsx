"use client";

import { useEffect, useState } from "react";

import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";
import { site } from "@/lib/site";

const names = ["acme", "northridge", "harbour-co", "delta-parts"];

function useTyped(words: string[], speed = 90, hold = 1400) {
  const [i, setI] = useState(0);
  const [text, setText] = useState("");
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const word = words[i % words.length];
    let t: ReturnType<typeof setTimeout>;
    if (!deleting && text === word) {
      t = setTimeout(() => setDeleting(true), hold);
    } else if (deleting && text === "") {
      t = setTimeout(() => {
        setDeleting(false);
        setI((n) => n + 1);
      }, speed * 2);
    } else {
      t = setTimeout(() => setText(word.slice(0, text.length + (deleting ? -1 : 1))), deleting ? speed / 2 : speed);
    }
    return () => clearTimeout(t);
  }, [text, deleting, i, words, speed, hold]);

  return text;
}

export function OnboardingSteps() {
  const typed = useTyped(names);
  return (
    <section id="how" className="scroll-mt-16">
      <div className="mx-auto max-w-[99rem] px-4 py-16 sm:px-8 sm:py-20">
        <Reveal>
          <SectionHeading
            number="04"
            eyebrow="Onboarding"
            title="Email first. Database second."
            lede="A signup that immediately provisions compute is how you get spam tenants. We wait for the verify click. Then we create a role, a database, migrate it, and put one owner in."
          />
        </Reveal>
        <ol className="mt-12 grid gap-px bg-line md:grid-cols-3">
          <Step n="1" title="Company details" body="Legal name, optional trading name, the hostname you want, owner email and password. Two acknowledgements: you may bind the company, and you have read that hosting is outside South Africa." />
          <Step n="2" title="Verify email" body="One link, 24 hours, single use. Until you click it there is no database and no workspace. Resend is capped." />
          <Step n="3" title="Empty workspace" body="Owner login only. No default till@ passwords, no sample locations. Import SKUs or start from zero. Cin7 and Xero shaped CSVs are in settings.">
            <div className="mt-5 border border-line bg-paper-2 px-3 py-2 font-mono text-sm" aria-live="polite">
              <span className="text-muted">https://</span>
              {typed}
              <span aria-hidden className="ml-px inline-block h-4 w-px animate-blink bg-ink align-middle" />
              <span className="text-muted">.{site.domain}</span>
            </div>
          </Step>
        </ol>
      </div>
    </section>
  );
}

function Step({ n, title, body, children }: { n: string; title: string; body: string; children?: React.ReactNode }) {
  return (
    <Reveal as="li" delay={(Number(n) - 1) * 0.05} className="bg-white p-6 sm:p-8">
      <span className="font-mono text-sm text-interactive">{n}</span>
      <h3 className="mt-4 text-xl font-medium">{title}</h3>
      <p className="mt-3 text-sm leading-relaxed text-muted">{body}</p>
      {children}
    </Reveal>
  );
}
