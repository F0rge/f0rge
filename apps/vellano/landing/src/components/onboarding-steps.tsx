"use client";

import { useEffect, useState } from "react";

import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";
import { site } from "@/lib/site";

const names = ["acme", "kramer-and-sons", "maboneng-living", "casa-bedfordview"];

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
    <section id="how" className="mx-auto max-w-7xl scroll-mt-20 px-5 py-24 sm:px-8 sm:py-32">
      <Reveal>
        <SectionHeading
          number="03"
          eyebrow="How onboarding works"
          title={
            <>
              Two minutes to a workspace that is <span className="display-italic">empty and yours.</span>
            </>
          }
        />
      </Reveal>
      <ol className="mt-14 grid gap-5 md:grid-cols-3">
        <Step n="1" title="Create your company" body="Legal name, trading name, the address you want, and one owner login. No card." />
        <Step n="2" title="Verify your email" body="One link, valid for 24 hours. We do not create anything until you click it." />
        <Step n="3" title="Open your workspace" body="Your own database, your own address. Add your first SKU or import from Cin7 or Xero.">
          <div className="mt-5 rounded-lg border border-line bg-white px-4 py-3 font-mono text-sm text-ink-2" aria-live="polite">
            <span className="text-terracotta">https://</span>
            <span>{typed}</span>
            <span aria-hidden className="ml-px inline-block h-4 w-px animate-blink bg-ink align-middle" />
            <span className="text-muted">.{site.domain}</span>
          </div>
        </Step>
      </ol>
    </section>
  );
}

function Step({ n, title, body, children }: { n: string; title: string; body: string; children?: React.ReactNode }) {
  return (
    <Reveal as="li" delay={(Number(n) - 1) * 0.08} className="relative rounded-2xl border border-line bg-white/60 p-7">
      <span className="font-display text-5xl text-terracotta mono-num">{n}</span>
      <h3 className="mt-5 text-2xl">{title}</h3>
      <p className="mt-3 text-sm leading-relaxed text-muted">{body}</p>
      {children}
    </Reveal>
  );
}
