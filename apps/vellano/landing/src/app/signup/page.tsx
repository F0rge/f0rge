import type { Metadata } from "next";

import { SignupForm } from "./signup-form";

export const metadata: Metadata = { title: "Create your company" };

export default function SignupPage() {
  return (
    <section className="mx-auto max-w-7xl px-5 py-12 sm:px-8 sm:py-20">
      <div className="max-w-2xl">
        <p className="eyebrow">Create your company</p>
        <h1 className="mt-4 text-4xl leading-[1.02] sm:text-5xl">
          Two minutes. <span className="display-italic">No card.</span>
        </h1>
        <p className="mt-4 text-lg text-muted">
          Tell us who the company is and where you want its workspace to live. We create nothing until you verify your email.
        </p>
      </div>
      <SignupForm />
    </section>
  );
}
