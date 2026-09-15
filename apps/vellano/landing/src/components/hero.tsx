import { ArrowRight } from "lucide-react";

import { ButtonLink } from "@/components/button";
import { Reveal } from "@/components/reveal";
import { WorkspaceMock } from "@/components/workspace-mock";

export function Hero() {
  return (
    <section className="grain relative overflow-hidden">
      <div className="mx-auto max-w-7xl px-5 pb-10 pt-16 sm:px-8 sm:pt-24">
        <Reveal className="max-w-4xl">
          <p className="eyebrow">Back office for furniture retail · South Africa</p>
          <h1 className="mt-6 text-[2.75rem] leading-[0.98] sm:text-6xl md:text-7xl lg:text-[5.5rem]">
            Stock, till, and books. <span className="display-italic">One back office</span> for furniture retailers.
          </h1>
          <p className="mt-7 max-w-2xl text-lg leading-relaxed text-muted sm:text-xl">
            Quotes to delivery to VAT201 — with your own workspace on your own address, and your data in your own database.
          </p>
          <div className="mt-9 flex flex-wrap items-center gap-3">
            <ButtonLink href="/signup" className="px-6 py-3.5 text-base">
              Create your company <ArrowRight size={16} />
            </ButtonLink>
            <ButtonLink href="/#how" variant="secondary" className="px-6 py-3.5 text-base">
              See how it works
            </ButtonLink>
          </div>
          <p className="mt-5 text-sm text-muted">No card. No payment yet. Two minutes to your own workspace.</p>
        </Reveal>
        <div className="mt-14 sm:mt-20">
          <WorkspaceMock />
        </div>
        <p className="mt-8 text-center text-sm text-muted">
          Trusted by <span className="text-ink">Vellano, Kramerville</span> — customer #1 since 2026.
        </p>
      </div>
    </section>
  );
}
