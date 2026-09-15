import type { Metadata } from "next";

import { SignupForm } from "./signup-form";

export const metadata: Metadata = { title: "Create a company" };

export default function SignupPage() {
  return (
    <section className="mx-auto max-w-[99rem] px-4 py-12 sm:px-8 sm:py-16">
      <div className="max-w-2xl">
        <p className="eyebrow">Create a company</p>
        <h1 className="mt-4 font-serif text-4xl leading-tight sm:text-5xl">Register the company. Verify later.</h1>
        <p className="mt-4 text-base text-muted sm:text-lg">
          Legal name, hostname, owner login. Nothing is provisioned until the verify link is clicked. There is no payment step.
        </p>
      </div>
      <SignupForm />
    </section>
  );
}
