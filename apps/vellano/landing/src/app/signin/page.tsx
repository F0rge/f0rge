import type { Metadata } from "next";

import { SigninPicker } from "./signin-picker";

export const metadata: Metadata = { title: "Sign in" };

export default function SigninPage() {
  return (
    <section className="mx-auto w-full max-w-2xl px-6 py-20 sm:px-10 sm:py-28 lg:px-16">
      <p className="eyebrow">Sign in</p>
      <h1 className="type-display mt-4 text-[2.25rem] sm:text-[3.375rem]">Which hostname?</h1>
      <p className="mt-5 text-base text-muted">
        Each company is a separate address. We send you to its login. This page does not look up your email across companies.
      </p>
      <SigninPicker />
    </section>
  );
}
