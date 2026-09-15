import type { Metadata } from "next";

import { SignupForm } from "./signup-form";

export const metadata: Metadata = { title: "Create a company" };

export default function SignupPage() {
  return (
    <section className="page-wrap py-12 sm:py-16">
      <div className="max-w-2xl">
        <p className="eyebrow">Create a company</p>
        <h1 className="type-display mt-4 text-[2.25rem] sm:text-[3.375rem]">Register the company. Verify later.</h1>
        <p className="mt-4 text-base text-muted">
          Legal name, hostname, owner login. Nothing is provisioned until the verify link is clicked. There is no payment
          step.
        </p>
      </div>
      <SignupForm />
    </section>
  );
}
