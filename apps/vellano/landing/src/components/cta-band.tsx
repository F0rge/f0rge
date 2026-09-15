import { ArrowRight } from "lucide-react";

import { ButtonLink } from "@/components/button";
import { Reveal } from "@/components/reveal";
import { site } from "@/lib/site";

export function CtaBand() {
  return (
    <section className="bg-ink text-white">
      <div className="mx-auto max-w-[99rem] px-4 py-16 sm:px-8 sm:py-20">
        <Reveal className="max-w-3xl">
          <p className="eyebrow !text-white/50">Next</p>
          <h2 className="mt-4 font-serif text-3xl leading-tight sm:text-4xl">
            Create the company. Verify the email. Get a hostname and an empty database.
          </h2>
          <p className="mt-4 max-w-xl text-base text-white/70">
            yourcompany.{site.domain} — no card, no sales call. If the slug is taken you will find out before submit.
          </p>
          <div className="mt-8 flex flex-wrap">
            <ButtonLink href="/signup" variant="header">
              Create a company workspace <ArrowRight size={16} />
            </ButtonLink>
            <ButtonLink href="/signin" variant="secondary">
              Sign in to an existing host
            </ButtonLink>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
