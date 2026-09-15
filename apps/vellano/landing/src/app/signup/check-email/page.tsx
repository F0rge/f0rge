import { MailCheck } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { ButtonLink } from "@/components/button";

export const metadata: Metadata = { title: "Check your email" };

export default async function CheckEmailPage({ searchParams }: { searchParams: Promise<{ email?: string; id?: string }> }) {
  const { email, id } = await searchParams;
  return (
    <section className="mx-auto max-w-2xl px-5 py-20 sm:px-8 sm:py-28">
      <span className="grid h-12 w-12 place-items-center rounded-full bg-ink text-paper">
        <MailCheck size={22} />
      </span>
      <p className="eyebrow mt-8">Step 2 of 3</p>
      <h1 className="mt-4 text-4xl leading-[1.02] sm:text-5xl">
        Check your <span className="display-italic">inbox.</span>
      </h1>
      <p className="mt-5 text-lg leading-relaxed text-muted">
        We sent a verification link to <strong className="font-medium text-ink">{email ?? "your email"}</strong>. Click it within 24 hours and
        we will set up your workspace. Nothing exists until you do.
      </p>
      <div className="mt-8 rounded-2xl border border-line bg-white/70 p-6 text-sm leading-relaxed text-muted">
        <p>Not there after a minute? Check spam, then resend.</p>
        <div className="mt-4 flex flex-wrap gap-3">
          <ButtonLink href={`/signup/check-email?email=${encodeURIComponent(email ?? "")}&id=${id ?? ""}&resent=1`} variant="secondary">
            Resend link
          </ButtonLink>
          <ButtonLink href={`/verify?token=demo-${id ?? "preview"}`} variant="ghost">
            Preview the verify step →
          </ButtonLink>
        </div>
      </div>
      <p className="mt-8 text-sm text-muted">
        Wrong address? <Link href="/signup" className="underline decoration-terracotta underline-offset-2">Start again</Link>.
      </p>
    </section>
  );
}
