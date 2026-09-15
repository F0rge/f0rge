import type { Metadata } from "next";

import { SigninPicker } from "./signin-picker";

export const metadata: Metadata = { title: "Sign in" };

export default function SigninPage() {
  return (
    <section className="mx-auto max-w-2xl px-4 py-16 sm:px-8 sm:py-24">
      <p className="eyebrow">Sign in</p>
      <h1 className="mt-4 font-serif text-4xl leading-tight sm:text-5xl">Which hostname?</h1>
      <p className="mt-5 text-base text-muted sm:text-lg">
        Each company is a separate address. We send you to its login. We do not look up your email across companies from this
        page.
      </p>
      <SigninPicker />
    </section>
  );
}
