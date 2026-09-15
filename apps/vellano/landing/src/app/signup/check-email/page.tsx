import type { Metadata } from "next";
import Link from "next/link";

import { ButtonLink } from "@/components/button";

export const metadata: Metadata = { title: "Check your email" };

export default async function CheckEmailPage({ searchParams }: { searchParams: Promise<{ email?: string; id?: string }> }) {
  const { email, id } = await searchParams;
  return (
    <section className="mx-auto w-full max-w-2xl px-4 py-16 sm:px-8 sm:py-24">
      <p className="eyebrow">Step 2 of 3</p>
      <h1 className="type-display mt-4 text-[2.25rem] sm:text-[3.375rem]">Open the email we sent.</h1>
      <p className="mt-5 text-base leading-relaxed text-muted">
        Verification goes to <strong className="font-medium text-ink">{email ?? "your email"}</strong>. The link lasts 24 hours
        and works once. Until then there is no database.
      </p>
      <div className="mt-8 border border-line bg-paper-2 p-6 text-sm leading-relaxed text-muted">
        <p>Not in the inbox after a minute — check spam, then resend. Resend is rate-limited.</p>
        <div className="mt-4 flex flex-wrap">
          <ButtonLink href={`/signup/check-email?email=${encodeURIComponent(email ?? "")}&id=${id ?? ""}&resent=1`} variant="secondary">
            Resend link
          </ButtonLink>
          <ButtonLink href={`/verify?token=demo-${id ?? "preview"}`} variant="ghost">
            Preview the verify step
          </ButtonLink>
        </div>
      </div>
      <p className="mt-8 text-sm text-muted">
        Wrong address?{" "}
        <Link href="/signup" className="text-interactive underline-offset-2 hover:underline">
          Start again
        </Link>
        .
      </p>
    </section>
  );
}
