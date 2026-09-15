import { ButtonLink } from "@/components/button";
import { site } from "@/lib/site";

export function CtaBand() {
  return (
    <section className="bg-ink text-white">
      <div className="page-wrap py-16 sm:py-20">
        <p className="eyebrow !text-[#8d8d8d]">Next</p>
        <h2 className="type-display mt-4 max-w-3xl text-[2rem] sm:text-[2.625rem]">
          Create the company. Verify the email. Get a hostname and an empty database.
        </h2>
        <p className="mt-4 max-w-xl text-base text-[#c6c6c6]">
          yourcompany.{site.domain} — no card. If the slug is taken you will find out before submit. Questions:{" "}
          {site.supportEmail}.
        </p>
        <div className="mt-8 flex flex-wrap">
          <ButtonLink href="/signup" variant="header">
            Create a company workspace
          </ButtonLink>
          <ButtonLink href="/signin" variant="secondary">
            Sign in to an existing host
          </ButtonLink>
        </div>
      </div>
    </section>
  );
}
