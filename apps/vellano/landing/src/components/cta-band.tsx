import { ArrowRight } from "lucide-react";

import { ButtonLink } from "@/components/button";
import { Reveal } from "@/components/reveal";
import { site } from "@/lib/site";

export function CtaBand() {
  return (
    <section className="mx-auto max-w-7xl px-5 py-24 sm:px-8 sm:py-32">
      <Reveal className="grain relative overflow-hidden rounded-3xl bg-terracotta px-7 py-16 text-paper sm:px-14 sm:py-24">
        <div className="relative z-10 max-w-3xl">
          <p className="eyebrow !text-paper/70">Start today</p>
          <h2 className="mt-5 text-4xl leading-[1.02] sm:text-6xl">
            Your company. <span className="font-display italic font-normal">Your address.</span> Your database.
          </h2>
          <p className="mt-6 max-w-xl text-lg text-paper/85">
            yourcompany.{site.domain} is two minutes and one email away. No payment, no sales call.
          </p>
          <div className="mt-9 flex flex-wrap gap-3">
            <ButtonLink href="/signup" className="bg-paper text-ink hover:bg-white">
              Create your company <ArrowRight size={16} />
            </ButtonLink>
            <ButtonLink href="/signin" variant="secondary" className="border-paper/40 text-paper hover:border-paper hover:bg-white/10">
              Sign in
            </ButtonLink>
          </div>
        </div>
        <div aria-hidden className="pointer-events-none absolute -right-20 -top-24 h-80 w-80 rounded-full border border-paper/20" />
        <div aria-hidden className="pointer-events-none absolute -bottom-32 right-20 h-96 w-96 rounded-full border border-paper/15" />
      </Reveal>
    </section>
  );
}
